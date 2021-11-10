import boto3
import os
import json
from botocore.exceptions import ClientError

try:
    POLLY_METADATA_STORE = os.environ['POLLY_METADATA_STORE']
except KeyError as e:
    print(f"Missing env variable: {e}")
    exit(1)

dynamo = boto3.resource("dynamodb")
polly_metadata_store = dynamo.Table(POLLY_METADATA_STORE)

def create_media_object(item):
    # "output/full/hls/62de657b-7884-4dc0-8286-b9b63c521351/template62de657b-7884-4dc0-8286-b9b63c521351.m3u8"
    # output/preview/62de657b-7884-4dc0-8286-b9b63c521351.mp4
    media_key = item['s3']['object']['key']
    media_type = media_key.split('/')[1]
    media_bucket = item['s3']['bucket']['name']
    
    if media_type == "preview":
        media_id = media_key.split("/")[2].replace(".mp4", ".json")
    elif media_type == "full":
        media_id = media_key.split("/")[3] + ".json"
    else:
        media_id = None
    
    return {
        "media_id": media_id,
        "media_type": media_type,
        "media_key": media_key,
        "media_bucket": media_bucket
    }

def ddb_value(item):
    return {
        "Value": item
    }

def is_successful_ops(media_object):
    return media_object["metadata_updated"]
    
def is_failed_ops(media_object):
    return not is_successful_ops(media_object)

def update_metadata(media_object):
    
    media_object['metadata_updated'] = False
    
    attribute_updates = {}
    full_path = f"s3://{media_object['media_bucket']}/{media_object['media_key']}"
    

    if media_object['media_type'] == "preview":
        attribute_updates['PreviewVideoFile'] = ddb_value(full_path)
    if media_object['media_type'] == "full":
        attribute_updates['FullVideoStream'] = ddb_value(full_path)
        
    print(attribute_updates)
        
    if len(attribute_updates) == 0:
        return media_object
        
    asset_id = media_object["media_id"]
    
    try:
        dynamo_response = polly_metadata_store.update_item(
            Key={"AssetId": asset_id},
            AttributeUpdates=attribute_updates,
        )
        media_object["metadata_updated"] = True
    except ClientError as e:
        print(e)
    
    return media_object

def handler(event, context):
    
    media_objects = [ create_media_object(item) for item in event['Records'] ]
    print(media_objects)
    updates = [ update_metadata(media_object) for media_object in media_objects ]
    print(updates)
    
    successful_ops = [is_successful_ops(update) for update in updates]
    failed_ops = [ is_failed_ops(update) for update in updates]
    
    return {
        "statusCode":200,
        "body": json.dumps({
            "SuccessfulOps" : successful_ops,
            "FailedOps": failed_ops
            
        }, default=str)
    }
    