import os
import subprocess
import pathlib
import boto3
import json
from botocore.exceptions import ClientError
from decimal import Decimal

try:
    POLLY_METADATA_STORE = os.environ['POLLY_METADATA_STORE']
except KeyError as e:
    print(f"Missing env variable: {e}")
    exit(1)

FFMPEG_PREVIEW_DURATION = int(os.environ.get("FFMPEG_PREVIEW_DURATION", 30))
FFMPEG_FADEOUT_DURATION = int(os.environ.get("FFMPEG_FADEOUT_DURATION",  3))

s3 = boto3.client("s3")
dynamo = boto3.resource("dynamodb")
polly_metadata_store = dynamo.Table(POLLY_METADATA_STORE)

ROOT_PATH = "/tmp"

def default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)

def create_media_object(pair):
    bucket, input_path = pair
    
    # input_path = "audio/full/$DOCUMENT_ID/$POLLY_GENERATED.mp3"
    
    input_split  = input_path.split("/")
    input_type   = input_split[0]               # audio
    input_format = input_split[1]               # full
    input_polly  = input_split[-1]              # $POLLY_GENERATED.mp3
    input_ext    = input_polly.split(".")[-1]   # mp3
    
    input_polly_no_ext = input_polly.replace(f".{input_ext}", "")
    
    # get anything between input_format and input_polly
    input_document = "/".join(input_split[2:-1]) 
    
    return {
        "s3_full_path": f"s3://{bucket}/{input_path}",
        "s3_path":f"{bucket}/{input_path}",
        "s3_bucket": bucket,
        "s3_key": input_path,
        "media_type": input_type,
        "media_format": input_format,
        "media_extension": input_ext,
        "media_polly_file": input_polly,
        "media_polly_no_extension": input_polly_no_ext,
        "media_document_id": input_document,
        # /tmp/audio/full/$DOCUMENT_ID
        "local_path": f"{ROOT_PATH}/{input_type}/{input_format}/{input_document}",
        # /tmp/audio/full/$DOCUMENT_ID/$POLLY_GENERATED.mp3
        "local_full_path": f"{ROOT_PATH}/{input_path}",
        # /tmp/audio/preview/$DOCUMENT_ID
        "local_preview_path": f"{ROOT_PATH}/{input_type}/preview/{input_document}",
        # /tmp/audio/preview/$DOCUMENT_ID/$POLLY_GENERATED.wav
        "local_preview_full_path": f"{ROOT_PATH}/{input_type}/preview/{input_document}/{input_polly_no_ext}.wav",
        "preview_s3_key":f"{input_type}/preview/{input_document}/{input_polly_no_ext}.wav",
        "preview_s3_full_path": f"s3://{bucket}/{input_type}/preview/{input_document}/{input_polly_no_ext}.wav"
    }

# pipeline_check : media_object["local_paths_exist"]
def create_local_paths(media_object):
    try:
        pathlib.Path(media_object["local_path"]).mkdir(parents=True, exist_ok=True)
        pathlib.Path(media_object["local_preview_path"]).mkdir(parents=True, exist_ok=True)
        media_object["local_paths_exist"] = True
    except:
        media_object["local_paths_exist"] = False
    return media_object

# pipeline_check : media_object["source_available"]
def download(media_object):
    
    media_object["source_available"] = False
    
    if media_object["local_paths_exist"]:
    
        bucket = media_object["s3_bucket"]
        key = media_object["s3_key"]
        filename = media_object["local_full_path"]
        
        with open(filename, "wb") as fp:
            s3.download_fileobj(bucket, key, fp)
            media_object["source_available"] = True

    return media_object

def get_duration(local_path):
    FFPROBE_COMMAND = [
        "./bin/ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "compact=print_section=0:nokey=1:escape=csv",
        "-show_entries",
        "format=duration",
        local_path
    ]
    
    p = subprocess.Popen(FFPROBE_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    out, err = p.communicate()
    # because ffprobe outputs on stdout stream by default, unlike ffmpeg lol

    return Decimal(str(float(out)))

# pipeline_check : media_object["preview_available"]
def fade_out(media_object):
    
    media_object["preview_available"] = False
    
    if media_object["source_available"]:
        
        filename_in  = media_object["local_full_path"]
        filename_out = media_object["local_preview_full_path"]
        
        media_object['full_narration_duration'] = get_duration(filename_in)
        
        start_position = FFMPEG_PREVIEW_DURATION - FFMPEG_FADEOUT_DURATION
        
        FFMPEG_COMMAND = [
            "./bin/ffmpeg",
            "-i",
            filename_in,
            # f"-af 'afade=t=out:st={start_position}:d={FFMPEG_FADEOUT_DURATION}'",
            f"-af",
            f"afade=t=out:st={start_position}:d={FFMPEG_FADEOUT_DURATION}",
            "-to",
            str(FFMPEG_PREVIEW_DURATION),
            filename_out
        ]
        
        print(" ".join(FFMPEG_COMMAND))
        
        p = subprocess.Popen(FFMPEG_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
        out, err = p.communicate()
        # because ffmpeg outputs on error stream by default
        print(err)
        
        if os.path.isfile(filename_out):
            media_object["preview_available"] = True
        
    return media_object

# pipeline_check : media_object["preview_uploaded"]
def upload(media_object):
    
    media_object["preview_uploaded"] = False
    
    if media_object["preview_available"]:
    
        bucket          = media_object["s3_bucket"]
        preview_s3_key  = media_object["preview_s3_key"]
        local_filename  = media_object["local_preview_full_path"]
    
        try:
            s3.upload_file(
                local_filename,
                bucket,
                preview_s3_key
            )
            
            media_object["preview_uploaded"] = True
        except ClientError as e:
            print(e)
        
    return media_object

def check_for_failure(media_object):
    media_object["processing_successful"] = False
    
    conditions = [
        media_object["local_paths_exist"],
        media_object["source_available"],
        media_object["preview_available"],
        media_object["preview_uploaded"]
    ]
    
    if all(conditions):
        media_object["processing_successful"] = True
    return media_object

def update_metadata(media_object):
    media_object["metadata_updated"] = False
    
    attribute_updates = {
        "FullNarration": {
            "Value": media_object["s3_full_path"]
        },
        "AudioPreview":{
            "Value": "FAILED"
        },
        "FullNarrationDurationInSeconds":{
            "Value": media_object["full_narration_duration"]
        }
    }
    
    if media_object["processing_successful"]:
        attribute_updates["AudioPreview"]["Value"] = media_object["preview_s3_full_path"]
    
    asset_id = media_object["media_document_id"]
    full_narration_s3_url = media_object["s3_full_path"]
    
    try:
        dynamo_response = polly_metadata_store.update_item(
            Key={"AssetId": asset_id},
            AttributeUpdates=attribute_updates,
        )
        media_object["metadata_updated"] = True
    except ClientError as e:
        print(e)
    
    return media_object

def is_successful_ops(media_object):
    if media_object["processing_successful"] and media_object["metadata_updated"]:
        return media_object
    return None

def is_failed_ops(media_object):
    if not media_object["processing_successful"] or not media_object["metadata_updated"]:
        return media_object
    return None

def handler(event, context):
    
    # input key: /audio/full/$DOCUMENT_ID/$POLLY_GENERATED.mp3
    
    Records = event["Records"]
    # assuming all objects are coming from the same bucket
    bucket = Records[0]["s3"]["bucket"]["name"]
    
    # [ "bucket_name", "audio/full/$DOCUMENT_ID/$POLLY_GENERATED.mp3" ]
    object_pairs = [ 
        [ bucket, x["s3"]["object"]["key"] ]
        for x in Records 
    ]
    
    media_objects = [ create_media_object(pair) for pair in object_pairs]
    
    # "/tmp/audio/full/$DOCUMENT_ID/$POLLY_GENERATED.mp3"
    print(media_objects)
    
    local_paths = [ create_local_paths(media_object) for media_object in media_objects]
    
    full_narrations = [ download(local_path) for local_path in local_paths ]
    
    # "/tmp/audio/preview/$DOCUMENT_ID/$POLLY_GENERATED.wav"
    previews = [ fade_out(full_narration) for full_narration in full_narrations ]
    
    uploads = [ upload(preview) for preview in previews]
    
    checks = [ check_for_failure(upload) for upload in uploads]
    
    updates = [ update_metadata(check) for check in checks]
    
    successful_ops = [is_successful_ops(update) for update in updates]
    failed_ops = [ is_failed_ops(update) for update in updates]
    
    print("****************RESULTS****************")
    
    print(successful_ops)
    print(failed_ops)
    
    return {
        "statusCode":200,
        "body": json.dumps({
            "SuccessfulOps" : successful_ops,
            "FailedOps": failed_ops
            
        }, default=default)
    }
