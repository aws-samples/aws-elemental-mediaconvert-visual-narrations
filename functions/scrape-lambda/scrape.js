const AWS = require('aws-sdk');
const axios = require('axios');
const cheerio = require('cheerio');
const uuid = require('uuid');
const qs = require('querystring');
const {JSDOM} = require('jsdom');
const {Voices} = require('./voices');
const { makeSRTFile } = require('./lib/SRT');
const {
    getRandomVoiceId,
    getUrlFromEvent,
    getDominantLanguage
} = require('./lib/utils');
const {
    VMAPBody,
    getKeywordsFromEntitiesString
} = require('./lib/VMAP');

const Comprehend = new AWS.Comprehend();
const S3         = new AWS.S3();
const Dynamo     = new AWS.DynamoDB.DocumentClient();

const OutputS3BucketName = process.env['OutputS3BucketName'];
const Table = process.env['Table'];
const FFMPEG_PREVIEW_DURATION = 
    parseInt(process.env['FFMPEG_PREVIEW_DURATION'], 10) || 30;
const ADS_URL = process.env['ADS_URL'] || 'https://ads.amazon.com';

const downloadArticleP =  
    url => axios.get(url)
        .then( ({data}) => data )
        .catch( _ => null );

exports.handler = async event => {
    
    const AssetId = `${uuid.v4()}.json`;
    
    const SuccessfulOps = [];
    const FailedOps = [];
    
    /* Download and Scrape article */
    const url = getUrlFromEvent(event);
    const article = await downloadArticleP(url);
    
    const dom = new JSDOM(article);
    
    const { document } = dom.window;

    const images = Array.from(
        document.querySelectorAll('.amp-wp-article-content > figure a')
    );
    
    const imagesURLs = images.map( ({href}) => href);
    
    const articleHeader = document.querySelector('.amp-wp-title').innerHTML;
    
    const titles = Array.from(
        document.querySelectorAll('.amp-wp-article-content > h2')
    );
    
    const titlesText = titles.map( ({innerHTML}) => innerHTML);
    titlesText.push("More info at aws.amazon.com");
    titlesText.unshift(articleHeader);
    
    const paragraphs = Array.from(
        document.querySelectorAll('.amp-wp-article-content > p')
    );
    
    const paragraphsText = cheerio.load(
        paragraphs
            .map( ({innerHTML}) => innerHTML )
            .reduce((memo, next) => memo += ` ${next}`, "")
        )
        .text();
    
    if(!paragraphsText || paragraphsText === ""){
        return {
            statusCode: 400,
            body: "Could not find text for the selected article"
        }
    }
    
    /* Comprehend - Language and Entities  */
    const ComprehendText = 
        paragraphsText?.length > 4096 ? 
            paragraphsText?.substring(4096) 
            : 
            paragraphsText;
    
    const LanguageParams = {
        Text: ComprehendText
    }
    
    let LanguageJob = null;
    
    try{
        LanguageJob = 
            await Comprehend.detectDominantLanguage(LanguageParams).promise();
            
        SuccessfulOps.push(LanguageJob);
    }catch(LanguageJobError){
        
        console.error(`Error while detecting language \n${LanguageJobError}`);
        FailedOps.push({
            error: LanguageJobError,
            LanguageJob,
            LanguageParams
        });
    }
    
    const dominantLanguage = getDominantLanguage(LanguageJob);
    
    const EntitiesParams = {
        Text: ComprehendText,
        LanguageCode: dominantLanguage.LanguageCode
    };
    
    let EntitiesJob = null;
    
    try{
        EntitiesJob = await Comprehend.detectEntities(EntitiesParams).promise();
        SuccessfulOps.push(EntitiesJob);
    }catch(EntitiesJobError){
        console.error(`Error while detecting entities \n${EntitiesJobError}`);
        FailedOps.push({
            error: EntitiesJobError,
            EntitiesJob,
            EntitiesParams
        });
    }
    
    const SRTFile = makeSRTFile(titlesText, FFMPEG_PREVIEW_DURATION);
    
    const SRTUploadParams = {
        Bucket: OutputS3BucketName,
        Key: `srt/preview/${AssetId}.srt`,
        Body: SRTFile
    };
    
    let SRTUploadJob = null;
    
    try{
        SRTUploadJob = await S3.upload(SRTUploadParams).promise();
        SuccessfulOps.push(SRTUploadJob);
    }catch(SRTUploadError){
        console.error(`Error while writing to S3 \n${SRTUploadError}`);
        FailedOps.push({
            error: SRTUploadError,
            SRTUploadJob,
            SRTUploadParams
        });
        return {
            statusCode: 500,
            SRTFile,
            FailedOps
        }
    }
    
    
    const ADSUrlWithKeywords = `${ADS_URL}?${qs.stringify({
        keywords: getKeywordsFromEntitiesString(EntitiesJob.Entities)
    })}`;
    const VMAPFile = VMAPBody(ADSUrlWithKeywords);
    
    const VMAPUploadParams = {
        Bucket: OutputS3BucketName,
        Key: `vmap/${AssetId}`,
        Body: VMAPFile
    };
    
    let VMAPUploadJob = null;
    
    try{
        VMAPUploadJob = await S3.upload(VMAPUploadParams).promise();
        SuccessfulOps.push(VMAPUploadJob);
    }catch(VMAPUploadError){
        console.error(`Error while writing to S3 \n${VMAPUploadError}`);
        FailedOps.push({
            error: VMAPUploadError,
            VMAPUploadJob,
            VMAPUploadParams
        });
        return {
            statusCode: 500,
            VMAPFile,
            FailedOps
        }
    }
    
    
    const {VoiceId, Neural, FullLanguageCode} = getRandomVoiceId(
        dominantLanguage.LanguageCode, Voices
    );
    
    /* Prepare Output and Upload */
    const OutputDocument = {
        AssetId,
        Text: paragraphsText,
        LanguageCode: FullLanguageCode,
        VoiceId,
        Engine: Neural ? "neural" : "standard",
        Url: url,
        ImagesURLs: imagesURLs,
        TitlesText: titlesText,
        Entities: EntitiesJob.Entities,
        SRTFile,
        VMAPFile
    };
    
    const UploadParams = {
        Bucket: OutputS3BucketName,
        Key: `text/${AssetId}`,
        Body: JSON.stringify(OutputDocument, null, 2)
    };
    
    let s3UploadJob = null;
    
    try{
        s3UploadJob = await S3.upload(UploadParams).promise();
        SuccessfulOps.push(s3UploadJob);
    }catch(s3UploadError){
        console.error(`Error while writing to S3 \n${s3UploadError}`);
        FailedOps.push({
            error: s3UploadError,
            s3UploadJob,
            UploadParams
        });
        return {
            statusCode: 500,
            OutputDocument,
            FailedOps
        }
    }
    
    /* Store in Metadata Store */
        
    const DDBParams = {
        "TableName":Table,
        Key:{
            AssetId
        },
        ExpressionAttributeNames: {
            "#bucket": "Bucket",
            "#fullNarration": "FullNarration",
            "#voiceId": "VoiceId",
            "#articlePath": "ArticlePath",
            "#languageCode":"LanguageCode",
            "#engine":"Engine",
            "#url":"Url"
        },
        ExpressionAttributeValues:{
            ":bucket": OutputS3BucketName,
            ":fullNarration": "NOT_STARTED",
            ":voiceId": VoiceId,
            ":articlePath": `s3://${OutputS3BucketName}/text/${AssetId}`,
            ":languageCode": FullLanguageCode,
            ":engine": Neural ? "neural" : "standard",
            ":url":url
        },
        UpdateExpression: `SET  #bucket = :bucket,
                                #fullNarration = :fullNarration,
                                #voiceId = :voiceId,
                                #articlePath = :articlePath,
                                #languageCode = :languageCode,
                                #engine = :engine,
                                #url = :url
                          `
    };
    
    let ddbResponse;
    try{
        ddbResponse = await Dynamo.update(DDBParams).promise();
    }catch(DDBError){
        console.error(`Error while writing to DDB \n${DDBError}`);
        FailedOps.push({
            error: DDBError,
            ddbResponse,
            DDBParams
        });
    }
    
    return {
        statusCode: 200,
        body:JSON.stringify(OutputDocument)
    };
};


async function main(){
    const fakeEvent = {
        body: JSON.stringify({
            Url: 'https://giusedroid.wordpress.com/2021/04/29/a-brief-history-of-ferrari/amp/'
        })
    };
    
    return exports.handler(fakeEvent);
}

if(!module.parent){
    main().then(x => console.log(JSON.stringify(x, null, 2)));
}
