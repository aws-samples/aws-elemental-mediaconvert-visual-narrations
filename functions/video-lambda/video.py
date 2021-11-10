import glob
import json
import os
import uuid
import boto3
import datetime
import random
from urllib.parse import urlparse
import logging
from datetime import timedelta

from botocore.client import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.resource('s3')

def humanize_time(secs):
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    return '%02d:%02d:%02d' % (hours, mins, secs)
    
def is_successful_ops(job_output):
    return job_output['statusCode'] == 200

def is_failed_ops(job_output):
    return job_output['statusCode'] != 200

def handler(event, context):
    
    job_outputs = [
        create_media_convert_jobs(record) for record in event['Records']
    ]
    
    successful_ops = [
        is_successful_ops(job_output) for job_output in job_outputs
    ]
    failed_ops =[
        is_failed_ops(job_output) for job_output in job_outputs
    ]
    
    return {
        'statusCode': 200,
        'body': json.dumps(
            {
                "JobOutputs":job_outputs,
                "FailedOps": failed_ops,
                "SuccessfulOps": successful_ops
                
            }, 
            indent=4, sort_keys=True, default=str
        )
    }
    

def create_media_convert_jobs(record):
   
    print(record)
    
    article_name = record['s3']['object']['key']
    article = urlparse(article_name)
    article = os.path.basename(article.path)
    filename = os.path.splitext(article)[0]
    
    logger.info("ARTICLE NAME")
    logger.info(article)
    
    # kept like this for readability
    assetID = article
    assetIDfull = article
    
    sourceS3Bucket = record['s3']['bucket']['name']
    templateS3URL = os.environ.get('TEMPLATE_S3_URL', 's3://gbatt-blogs/narratives/template.mov')
    templateS3URL_preview = os.environ.get('TEMPLATE_S3_URL_PREVIEW', 's3://gbatt-blogs/narratives/Template_video_right.mov')
    
    # reading the article json
    content_object = s3.Object(sourceS3Bucket, article_name)
    file_content = content_object.get()['Body'].read().decode('utf-8')
    json_content = json.loads(file_content)
    
    audiopreview = (json_content['Metadata']['AudioPreview'])
    photopreview1 = (json_content['Metadata']['PostProducedImagesS3Paths'][0])
    photopreview2 = (json_content['Metadata']['PostProducedImagesS3Paths'][1])
    photopreview3 = (json_content['Metadata']['PostProducedImagesS3Paths'][2])
    photopreview4 = (json_content['Metadata']['PostProducedImagesS3Paths'][3])
    audiofull = (json_content['Metadata']['FullNarration'])
    narrationlenght = (json_content['Metadata']['FullNarrationDurationInSeconds'])

    f = int(float(narrationlenght))
    partial=f//4

    framerate1=partial
    framerate2=framerate1+partial
    framerate3=framerate2+partial
    framerate4=framerate3+partial
   
    imagetimefull1=humanize_time(framerate1)+":00"
    imagetimefull2=humanize_time(framerate2)+":00"
    imagetimefull3=humanize_time(framerate3)+":00"
    imagetimefull4=humanize_time(framerate4)+":00"
    fullvideolenght = humanize_time(f+1)+":00"

    destinationS3 = f"s3://{os.environ['DestinationBucket']}"
    mediaConvertRole = os.environ['MediaConvertRole']
    application = os.environ['Application']
    region = os.environ['AWS_DEFAULT_REGION']
    statusCode = 200
    
    jobs = []
    jobsfull = []
    
    job = {}
    jobfull = {}
    
    # Use MediaConvert SDK UserMetadata to tag jobs with the assetID
    # Events from MediaConvert will have the assetID in UserMedata
    jobMetadata = {}
    jobMetadata['assetID'] = assetID
    jobMetadata['application'] = application
    jobMetadata['input'] = templateS3URL_preview
    
    jobMetadatafull = {}
    jobMetadatafull['assetID'] = assetIDfull
    jobMetadatafull['application'] = application
    jobMetadatafull['input'] = templateS3URL

    try:    

        # Build a list of jobs to run against the input by using the default job in this folder.
        jobInput = {}
        jobInputfull = {}

        bucket = s3.Bucket(sourceS3Bucket)
    
        # PREVIEW
        with open('preview_mp4.json') as json_data:
            jobInput['filename'] = 'Default'
            logger.info('jobInput: %s', jobInput['filename'])
            jobInput['settings'] = json.load(json_data)
            logger.info(json.dumps(jobInput['settings']))

            jobs.append(jobInput)
        
        # FULL VIDEO
        with open('full_hls.json') as json_datafull:
            jobInputfull['filename'] = 'Default'
            logger.info('jobInputfull: %s', jobInputfull['filename'])
            jobInputfull['settings'] = json.load(json_datafull)
            logger.info(json.dumps(jobInputfull['settings']))

            jobsfull.append(jobInputfull)
        
        endpoints = boto3.client('mediaconvert', region_name=region).describe_endpoints()

        client = boto3.client('mediaconvert', region_name=region, endpoint_url=endpoints['Endpoints'][0]['Url'], verify=False)

        for j in jobs:
            jobSettings = j['settings']
            jobFilename = j['filename']
            # Save the name of the settings file in the job userMetadata
            jobMetadata['settings'] = jobFilename

            # Update the job settings with the source video from the S3 event
            jobSettings['Inputs'][0]['FileInput'] = templateS3URL_preview
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][0]['ImageInserterInput'] = photopreview1
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][1]['ImageInserterInput'] = photopreview2
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][2]['ImageInserterInput'] = photopreview3
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][3]['ImageInserterInput'] = photopreview4
            jobSettings['Inputs'][0]['AudioSelectors']['Audio Selector 1']['ExternalAudioFileInput'] = audiopreview
            
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][0]['Width'] = 1100
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][1]['Width'] = 1100
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][2]['Width'] = 1100
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][3]['Width'] = 1100
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][0]['Height'] = 800
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][1]['Height'] = 800
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][2]['Height'] = 800
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][3]['Height'] = 800
            
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][0]['ImageX'] = 10
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][1]['ImageX'] = 10
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][2]['ImageX'] = 10
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][3]['ImageX'] = 10
            
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][0]['ImageY'] = 10
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][1]['ImageY'] = 10
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][2]['ImageY'] = 10
            jobSettings['Inputs'][0]['ImageInserter']['InsertableImages'][3]['ImageY'] = 10
            
            jobSettings['Inputs'][0]['CaptionSelectors']['Captions Selector 1']['SourceSettings']['FileSourceSettings']['SourceFile'] = f"s3://{sourceS3Bucket}/srt/preview/{article}.srt"
            jobSettings['OutputGroups'][0]['Outputs'][0]['CaptionDescriptions'][0]['DestinationSettings']['BurninDestinationSettings']['FontColor'] = "BLACK"
            jobSettings['OutputGroups'][0]['Outputs'][0]['CaptionDescriptions'][0]['DestinationSettings']['BurninDestinationSettings']['YPosition'] = 900
            
            logger.info('SRT FILE PAHT')
            logger.info(jobSettings['Inputs'][0]['CaptionSelectors']['Captions Selector 1']['SourceSettings']['FileSourceSettings']['SourceFile'])
            # Update the job settings with the destination paths for converted videos.  We want to replace the
            # destination bucket of the output paths in the job settings, but keep the rest of the
            # path
            destinationS3 = f"s3://{os.environ['DestinationBucket']}/output/preview/{filename}" 

            for outputGroup in jobSettings['OutputGroups']:

                logger.info("outputGroup['OutputGroupSettings']['Type'] == %s", outputGroup['OutputGroupSettings']['Type'])

                if outputGroup['OutputGroupSettings']['Type'] == 'FILE_GROUP_SETTINGS':
                    templateDestination = outputGroup['OutputGroupSettings']['FileGroupSettings']['Destination']
                    templateDestinationKey = urlparse(templateDestination).path
                    logger.info("templateDestinationKey == %s", templateDestinationKey)
                    outputGroup['OutputGroupSettings']['FileGroupSettings']['Destination'] = destinationS3
                else:
                    logger.error("Exception: Unknown Output Group Type %s", outputGroup['OutputGroupSettings']['Type'])
                    statusCode = 500
                    
            logger.info(json.dumps(jobSettings))

            # Convert the video using AWS Elemental MediaConvert
            job = client.create_job(Role=mediaConvertRole, UserMetadata=jobMetadata, Settings=jobSettings)

        #full video
        for j in jobsfull:
            jobSettingsfull = j['settings']
            jobFilenamefull = j['filename']

            # Save the name of the settings file in the job userMetadata
            jobMetadatafull['settings'] = jobFilenamefull

            # Update the job settings with the source video from the S3 event
            jobSettingsfull['Inputs'][0]['FileInput'] = templateS3URL
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][0]['ImageInserterInput'] = photopreview1
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][1]['ImageInserterInput'] = photopreview2
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][2]['ImageInserterInput'] = photopreview3
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][3]['ImageInserterInput'] = photopreview4
            jobSettingsfull['Inputs'][0]['AudioSelectors']['Audio Selector 1']['ExternalAudioFileInput'] = audiofull
            jobSettingsfull['Inputs'][0]['InputClippings'][0]['EndTimecode'] = fullvideolenght
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][0]['StartTime'] = "00:00:00:00"
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][1]['StartTime'] = imagetimefull1
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][2]['StartTime'] = imagetimefull2
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][3]['StartTime'] = imagetimefull3
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][0]['Duration'] = partial*1000
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][1]['Duration'] = partial*1000
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][2]['Duration'] = partial*1000
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][3]['Duration'] = partial*1000
            jobSettingsfull['OutputGroups'][0]['Outputs'][0]['NameModifier'] = filename
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][0]['Width'] = 1100
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][1]['Width'] = 1100
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][2]['Width'] = 1100
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][3]['Width'] = 1100
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][0]['Height'] = 800
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][1]['Height'] = 800
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][2]['Height'] = 800
            jobSettingsfull['Inputs'][0]['ImageInserter']['InsertableImages'][3]['Height'] = 800


            # Update the job settings with the destination paths for converted videos.  We want to replace the
            # destination bucket of the output paths in the job settings, but keep the rest of the
            # path
            destinationS3full = f"s3://{os.environ['DestinationBucket']}/output/full/hls/{filename}/"

            for outputGroup in jobSettingsfull['OutputGroups']:

                logger.info("outputGroup['OutputGroupSettings']['Type'] == %s", outputGroup['OutputGroupSettings']['Type'])

                if outputGroup['OutputGroupSettings']['Type'] == 'HLS_GROUP_SETTINGS':
                    templateDestination = outputGroup['OutputGroupSettings']['HlsGroupSettings']['Destination']
                    templateDestinationKey = urlparse(templateDestination).path
                    logger.info("templateDestinationKey == %s", templateDestinationKey)
                    outputGroup['OutputGroupSettings']['HlsGroupSettings']['Destination'] = destinationS3full
                else:
                    logger.error("Exception: Unknown Output Group Type %s", outputGroup['OutputGroupSettings']['Type'])
                    statusCode = 500
                    
            
                    
            logger.info(json.dumps(jobSettingsfull))

            # Convert the video using AWS Elemental MediaConvert
            jobfull = client.create_job(Role=mediaConvertRole, UserMetadata=jobMetadatafull, Settings=jobSettingsfull)

    except Exception as e:
        logger.error('Exception: %s', e)
        statusCode = 500

    finally:
        return {
            'statusCode': statusCode,
            'body': json.dumps({"previewJob":job, "fullJob":jobfull}, indent=4, sort_keys=True, default=str)
        }

# def create_media_tailor_jobs(event, context):

#     # expected $ORIGINAL_KEY/ads/$TYPE/$UUID.vmap.xml
#     KEY = urllib.unquote_plus(event["Records"][0]["s3"]["object"]["key"])
#     # expected [$ORIGINAL_KEY, $TYPE/$UUID.vmap.xml]
#     MEDIA_BUCKET, FILENAME = KEY.split("/ads/")
#     TYPE, UUID = FILENAME.split("/")
#     UUID = UUID.replace(".vmap.xml", "")

#     print("**********DYNAMO REQUEST**********")
#     try:
#         item = metadata_table.get_item(Key={"MediaId": UUID})["Item"]
#     except ClientError as e:
#         print(e)
#         return {
#             "statusCode": 500,
#             "body": f"possible problem with UUID {UUID}: {str(e)}",
#         }

#     print("**********DYNAMO RESPONSE**********")
#     print(json.dumps(item, indent=2, cls=DateTimeEncoder))

#     print("**********MEDIATAILOR REQUEST**********")
#     try:
#         mediatailor_response = mediatailor.put_playback_configuration(
#             AdDecisionServerUrl=item[f"VMAPUrl-{TYPE}"],
#             Name=f"{TYPE}-{UUID}",
#             Tags={"OriginTable": METADATA_TABLE, "MediaId": UUID},
#             VideoContentSourceUrl=item["PlaylistUrl"].replace("/playlist.m3u8", ""),
#         )
#     except ClientError as e:
#         print(e)
#         return {
#             "statusCode": 500,
#             "body": f"possible problem with UUID {UUID} and ads manifest type {TYPE}: {str(e)}",
#         }
#     except KeyError as e:
#         print(e)
#         return {
#             "statusCode": 500,
#             "body": f"ads manifest type {TYPE} not found for media {UUID}: {str(e)}",
#         }

#     print("**********MEDIATAILOR RESPONSE**********")
#     print(json.dumps(mediatailor_response, indent=2, cls=DateTimeEncoder))

#     print("**********DYNAMO UPDATE**********")
#     try:
#         update_response = metadata_table.update_item(
#             Key={"MediaId": UUID},
#             AttributeUpdates={
#                 f"StreamUrl-{TYPE}": {
#                     "Value": mediatailor_response["HlsConfiguration"][
#                         "ManifestEndpointPrefix"
#                     ]
#                 }
#             },
#         )
#     except ClientError as e:
#         print(e)
#         exit(255)

#     print("**********DYNAMO RESPONSE**********")
#     print(json.dumps(update_response, indent=2, cls=DateTimeEncoder))

#     return {"statusCode": 200, "body": "OK"}