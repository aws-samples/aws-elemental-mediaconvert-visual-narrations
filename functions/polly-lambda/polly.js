const AWS = require('aws-sdk');

const Polly  = new AWS.Polly();
const S3     = new AWS.S3();
const Dynamo = new AWS.DynamoDB.DocumentClient();

const getBucket = Record => Record.s3.bucket.name;
const getKey    = Record => Record.s3.object.key;

const {OutputS3BucketName, Table} = process.env;

exports.handler = async event => {
    const {Records} = event;
    
    const SuccessfulOps  = [];
    const FailedOps      = [];
    
    for (const Record of Records){
        
        const Bucket = getBucket(Record);
        const Key    = getKey(Record);
        
        let File;
        try{
            File = await S3.getObject({
                Key,
                Bucket
            }).promise();
            
        }catch(S3Error){
            console.error(`Error while retrieving file from S3 \n${S3Error}`);
            FailedOps.push({
                error: S3Error,
                Record
            });
            continue;
        }
        
        const {Text, VoiceId, Engine, LanguageCode} = JSON.parse(File.Body.toString());
        
        const PollyJobParams = {
            OutputFormat: "mp3",
            OutputS3BucketName, 
            Text,
            VoiceId,
            Engine,
            LanguageCode, // it's ok if it's null or undefined
            OutputS3KeyPrefix: `audio/full/${Key.replace('text/', '')}/`,
            TextType: "text"
        };
        
        let PollyJob;
        
        try{
            PollyJob = await Polly.startSpeechSynthesisTask(PollyJobParams).promise();
        }catch(PollyError){
            console.error(`Error while creating PollyJob \n${PollyError}`);
            FailedOps.push({
                error: PollyError,
                Record,
                PollyJob
            });
            continue;
        }
        const DDBParams = {
            "TableName":Table,
            Key:{
                AssetId: Key.replace("text/", "")
            },
            ExpressionAttributeNames: {
                "#fullNarration": "FullNarration"
            },
            ExpressionAttributeValues:{
                ":fullNarration": "IN_PROGRESS"
            },
            UpdateExpression: `SET #fullNarration = :fullNarration`
        };
        
        let ddbResponse;
        try{
            ddbResponse = await Dynamo.update(DDBParams).promise();
        }catch(DDBError){
            console.error(`Error while writing to DDB \n${DDBError}`);
            FailedOps.push({
                error: DDBError,
                Record,
                ddbResponse
            });
            continue;
        }
        
        SuccessfulOps.push({
            Record
        });
    }
    
    console.log("SuccessfulOps");
    console.log(JSON.stringify(SuccessfulOps, null, 2));
    console.log("FailedOps");
    console.log(JSON.stringify(FailedOps, null, 2));
    
    return {
        statusCode: 200,
        body: JSON.stringify({
            SuccessfulOps,
            FailedOps
        })
    }
}