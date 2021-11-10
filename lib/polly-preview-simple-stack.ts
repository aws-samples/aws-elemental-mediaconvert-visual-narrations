import * as cdk from '@aws-cdk/core';
import * as lambda from '@aws-cdk/aws-lambda';
import * as s3 from '@aws-cdk/aws-s3';
import * as lambdaEvent from '@aws-cdk/aws-lambda-event-sources';
import * as iam from '@aws-cdk/aws-iam';
import * as dynamo from '@aws-cdk/aws-dynamodb';
import * as apigateway from '@aws-cdk/aws-apigateway';
import { Duration } from '@aws-cdk/core';

const FFMPEG_PREVIEW_DURATION = "30";
const FFMPEG_FADEOUT_DURATION = "3";

export class PollyPreviewSimpleStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    
    const PollyAssetStore = new s3.Bucket(this, "PollyAssetStore", {
      enforceSSL: true,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED
    });
    const PollyMetadataStore = new dynamo.Table(this, "PollyMetadataStore", {
      partitionKey:{
        name: 'AssetId',
        type: dynamo.AttributeType.STRING
      }
    });
    
    const MediaConvertManagedPolicy = iam.ManagedPolicy.fromManagedPolicyArn(
      this, "MediaConvertManagedPolicy", 
      "arn:aws:iam::aws:policy/AWSElementalMediaConvertFullAccess"
    );
    
    const S3MediaConvertPolicyStatementRead = new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        "s3:Get*",
        "s3:List*"
      ],
      resources: [
        PollyAssetStore.bucketArn,
        `${PollyAssetStore.bucketArn}/*`,
        "arn:aws:s3:::gbatt-blogs/narratives",
        "arn:aws:s3:::gbatt-blogs/narratives/*"
      ]
    });
    
    const S3MediaConvertPolicyStatementWrite = new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        "s3:Put*",
        "s3:*MultipartUpload*"
      ],
      resources: [
        PollyAssetStore.bucketArn,
        `${PollyAssetStore.bucketArn}/*`
      ]
    });
    
    const S3MediaConvertInlinePolicy = new iam.PolicyDocument({
      statements: [
        S3MediaConvertPolicyStatementRead,
        S3MediaConvertPolicyStatementWrite
      ]
    });
    
    const MediaconvertPassDownRole = new iam.Role(
      this,
      "MediaconvertPassDownRole", 
      {
        assumedBy: new iam.ServicePrincipal('mediaconvert.amazonaws.com'),
        managedPolicies: [
          MediaConvertManagedPolicy
        ],
        inlinePolicies: {
          "S3MediaConvertInline": S3MediaConvertInlinePolicy
        }
      });
    
    const ScrapeLambda = new lambda.Function(this, "ScrapeLambda", {
      code: lambda.Code.fromAsset("functions/scrape-lambda"),  
      handler: "scrape.handler", 
      runtime: lambda.Runtime.NODEJS_14_X,
      memorySize: 512,
      timeout: Duration.seconds(29),
      environment: {
        Table : PollyMetadataStore.tableName,
        OutputS3BucketName: PollyAssetStore.bucketName,
        FFMPEG_PREVIEW_DURATION,
        FFMPEG_FADEOUT_DURATION
      }
    });
    
    const ScrapeApi = new apigateway.RestApi(this, "scrape-api", {
      restApiName: "Scraping Service",
      description: "This service starts scraping an article."
    });
    
    const postScrapeIntegration = new apigateway.LambdaIntegration(ScrapeLambda, {
      requestTemplates: { "application/json": '{ "statusCode": "200" }' }
    });

    ScrapeApi.root.addMethod("POST", postScrapeIntegration);
    
    const PollyLambda = new lambda.Function(this, "PollyLambda", {
      code: lambda.Code.fromAsset("functions/polly-lambda"),  
      handler: "polly.handler", 
      runtime: lambda.Runtime.NODEJS_14_X,
      memorySize: 512,
      environment: {
        Table : PollyMetadataStore.tableName,
        OutputS3BucketName: PollyAssetStore.bucketName
      }
    });
    
    const FadeOutLambda = new lambda.Function(this, "FadeOutLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("functions/postprod-lambda"),
      handler: "fadeout.handler",
      memorySize: 512,
      environment: {
        POLLY_METADATA_STORE : PollyMetadataStore.tableName,
        FFMPEG_PREVIEW_DURATION,
        FFMPEG_FADEOUT_DURATION
      }
    });
    
    const ImagesLambda = new lambda.Function(this, "ImagesLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("functions/postprod-lambda"),
      handler: "images.handler",
      timeout:  Duration.seconds(90),
      memorySize: 2048,
      environment: {
        POLLY_METADATA_STORE : PollyMetadataStore.tableName
      }
    });
    
    const VideoLambda = new lambda.Function(this, "VideoLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("functions/video-lambda"),
      handler: "video.handler",
      memorySize: 512,
      environment: {
        POLLY_METADATA_STORE : PollyMetadataStore.tableName,
        DestinationBucket: PollyAssetStore.bucketName,
        Application: "VOD",
        MediaConvertRole: MediaconvertPassDownRole.roleArn,
        // TEMPLATE_S3_URL: "s3://your/custom/template/here.mp4",
        // TEMPLATE_S3_URL_PREVIEW: "s3://your/custom/template/here.mp4",
      }
    });
    
    const FinalizeUpdateLambda = new lambda.Function(this, "FinalizeUpdateLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("functions/finalize-lambda"),
      handler: "finalize.handler",
      memorySize: 512,
      environment: {
        POLLY_METADATA_STORE : PollyMetadataStore.tableName
      }
    });
    
    const OnTextUpload = new lambdaEvent.S3EventSource(PollyAssetStore, {
      events: [
        s3.EventType.OBJECT_CREATED
      ], 
      filters: [
        {
          prefix: 'text'
        },
        {
          suffix: 'json'
        }
      ]
    });
    
    const OnFullAudioUpload = new lambdaEvent.S3EventSource(PollyAssetStore, {
      events: [
        s3.EventType.OBJECT_CREATED
      ],
      filters: [
        {
          prefix: 'audio/full'
        },
        {
          suffix: 'mp3'
        }
      ]
    });
    
    const OnPreviewAudioUpload = new lambdaEvent.S3EventSource(PollyAssetStore, {
      events: [
        s3.EventType.OBJECT_CREATED
      ],
      filters: [
        {
          prefix: 'audio/preview'
        },
        {
          suffix: 'wav'
        }
      ]
    });
    
    const OnVideoTriggerUpload = new lambdaEvent.S3EventSource(PollyAssetStore, {
      events: [
        s3.EventType.OBJECT_CREATED
      ],
      filters: [
        {
          prefix: 'video-trigger'
        },
        {
          suffix: 'json'
        }
      ]
    });
    
    const OnVideoPreviewUpload = new lambdaEvent.S3EventSource(PollyAssetStore, {
      events: [
        s3.EventType.OBJECT_CREATED
      ],
      filters: [
        {
          prefix: 'output/preview'
        },
        {
          suffix: 'mp4'
        }
      ]
    });
    
    const OnVideoFullNarrationUpload = new lambdaEvent.S3EventSource(PollyAssetStore, {
      events: [
        s3.EventType.OBJECT_CREATED
      ],
      filters: [
        {
          prefix: 'output/full/hls'
        },
        {
          suffix: 'm3u8'
        }
      ]
    });
    
    PollyLambda.addEventSource(OnTextUpload);
    FadeOutLambda.addEventSource(OnFullAudioUpload);
    ImagesLambda.addEventSource(OnPreviewAudioUpload);
    VideoLambda.addEventSource(OnVideoTriggerUpload);
    FinalizeUpdateLambda.addEventSource(OnVideoPreviewUpload);
    FinalizeUpdateLambda.addEventSource(OnVideoFullNarrationUpload);
    
    const pollyPolicy : iam.PolicyStatement = new iam.PolicyStatement();
    pollyPolicy.addActions("polly:startSpeechSynthesisTask");
    pollyPolicy.addResources("*");
    
    const comprehendPolicy : iam.PolicyStatement = new iam.PolicyStatement();
    comprehendPolicy.addActions("comprehend:detect*");
    comprehendPolicy.addResources("*");
    
    const passDownRole : iam.PolicyStatement = new iam.PolicyStatement();
    passDownRole.addActions('iam:PassRole');
    passDownRole.addResources(MediaconvertPassDownRole.roleArn);
    
    VideoLambda.role?.addManagedPolicy(MediaConvertManagedPolicy);
    VideoLambda.addToRolePolicy(passDownRole);
    
    PollyLambda.addToRolePolicy(pollyPolicy);
    ScrapeLambda.addToRolePolicy(comprehendPolicy);

    PollyAssetStore.grantRead(PollyLambda);
    PollyAssetStore.grantRead(FadeOutLambda);
    PollyAssetStore.grantRead(ScrapeLambda);
    PollyAssetStore.grantRead(ImagesLambda);
    PollyAssetStore.grantRead(VideoLambda);
    
    PollyAssetStore.grantPut(PollyLambda);
    PollyAssetStore.grantPut(FadeOutLambda);
    PollyAssetStore.grantPut(ScrapeLambda);
    PollyAssetStore.grantPut(ImagesLambda);
    PollyAssetStore.grantPut(VideoLambda);

    PollyMetadataStore.grantReadWriteData(PollyLambda);
    PollyMetadataStore.grantReadWriteData(FadeOutLambda);
    PollyMetadataStore.grantReadWriteData(ScrapeLambda);
    PollyMetadataStore.grantReadWriteData(ImagesLambda);
    PollyMetadataStore.grantReadWriteData(VideoLambda);
    PollyMetadataStore.grantReadWriteData(FinalizeUpdateLambda);
  
    const APIEndpointOutput = new cdk.CfnOutput(
      this, 'APIEndpoint', {
        value: ScrapeApi.url
      }
    );
    
    const AssetStoreBucketNameOutput = new cdk.CfnOutput(
      this, 'AssetStoreBucketName', {
        value: PollyAssetStore.bucketName
      });
      
    const AssetStoreBucketArnOutput = new cdk.CfnOutput(
      this, 'AssetStoreBucketArn', {
        value: PollyAssetStore.bucketArn
      });
      
    const MetadataStoreOutput = new cdk.CfnOutput(
      this, 'MetadataStoreName', {
        value: PollyMetadataStore.tableName
      }  
    );
  }
}
