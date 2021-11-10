import os
import subprocess
import pathlib
import boto3
import json
import urllib.request
from botocore.exceptions import ClientError
from decimal import Decimal

try:
    POLLY_METADATA_STORE = os.environ['POLLY_METADATA_STORE']
except KeyError as e:
    print(f"Missing env variable: {e}")
    exit(1)

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
    
    # input_path = "audio/preview/$DOCUMENT_ID/$POLLY_GENERATED.wav"
    
    input_split  = input_path.split("/")
    input_type   = input_split[0]               # audio
    input_format = input_split[1]               # preview
    input_polly  = input_split[-1]              # $POLLY_GENERATED.wav
    input_ext    = input_polly.split(".")[-1]   # wav
    
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
        "source_local_path": f"{ROOT_PATH}/source/{input_document}",
        "output_local_path": f"{ROOT_PATH}/output/{input_document}",
        "source_s3_path": f"s3://{bucket}/image/source/{input_document}",
        "output_s3_path": f"s3://{bucket}/image/output/{input_document}",
        "output_s3_key":  f"image/output/{input_document}",
        "article_s3_path": f"s3://{bucket}/text/{input_document}",
        "article_s3_key": f"text/{input_document}",
        "article_local_path": f"{ROOT_PATH}/source/{input_document}/{input_document}", # by design is /tmp/source/article.json/article/json
        "video_trigger_local_path": f"{ROOT_PATH}/output/{input_document}/{input_document}",
        "video_trigger_s3_path": f"s3://{bucket}/video-trigger/{input_document}",
        "video_trigger_s3_key": f"video-trigger/{input_document}"
    }

# pipeline_check : media_object["local_paths_exist"]
def create_local_paths(media_object):
    try:
        pathlib.Path(media_object["source_local_path"]).mkdir(parents=True, exist_ok=True)
        pathlib.Path(media_object["output_local_path"]).mkdir(parents=True, exist_ok=True)
        media_object["local_paths_exist"] = True
    except:
        media_object["local_paths_exist"] = False
    return media_object

# pipeline_check : media_object["article_available"]
def download_article_object(media_object):
    
    media_object["article_available"] = False
    
    if media_object["local_paths_exist"]:
    
        bucket = media_object["s3_bucket"]
        key = media_object["article_s3_key"]
        filename = media_object["article_local_path"]
        
        with open(filename, "wb") as fp:
            s3.download_fileobj(bucket, key, fp)
            media_object["article_available"] = True

    return media_object

# pipeline_check : media_object["source_images_available"]
def download_images(media_object):
    
    media_object["source_images_available"] = False
    
    if media_object["article_available"]:
        
        media_object["source_images_local_paths"] = []
        
        with open(media_object["article_local_path"]) as fp:
            json_object = json.load(fp)
            media_object["article_body"] = json_object
            media_object["images_urls"] = json_object["ImagesURLs"]
    
        # downloading only the first 4 images
        for url in media_object["images_urls"][:4]:
            source_filename = url.split("/")[-1]
            output_filename = f"{media_object['source_local_path']}/{source_filename}"
            
            http_response = urllib.request.urlopen(url)
            with open(output_filename, "wb") as fp:
                fp.write(http_response.read())
            media_object["source_images_local_paths"].append(output_filename)
        
        media_object["source_images_available"] = True
    
    return media_object
            
def convert_image(input_path, output_path):
    FFMPEG_COMMAND = [
        "./bin/ffmpeg",
        "-i",
        input_path,
        output_path
    ]
    
    print(" ".join(FFMPEG_COMMAND))
        
    p = subprocess.Popen(FFMPEG_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    out, err = p.communicate()
    # because ffmpeg outputs on error stream by default
    print(err)
        
    if os.path.isfile(output_path):
        return output_path
    return None

# pipeline_check : media_object["output_images_available"]
def convert_images(media_object):
    
    media_object["output_images_available"] = False
    
    if media_object["source_images_available"]:
        media_object["output_images_local_paths"] = [
            convert_image(image_filename, f"{image_filename}.tga")
            for image_filename in media_object["source_images_local_paths"]
        ]
        
        if any(media_object["output_images_local_paths"]):
            media_object["output_images_available"] = True
    
    return media_object

def upload_image(local_path, bucket, key):
    try:
        s3.upload_file(
            local_path,
            bucket,
            key
        )
        
    except ClientError as e:
        print(e)
        return None
    
    return f"s3://{bucket}/{key}"

# pipeline_check : media_object["images_uploaded"]
def upload(media_object):
    
    media_object["images_uploaded"] = False
    
    if media_object["output_images_available"]:
        
        bucket = media_object["s3_bucket"]
        output_key = media_object["output_s3_key"]
        get_filename = lambda x : x.split("/")[-1]
        
        media_object["output_images_s3_paths"] = [
            upload_image(
                output_image_local_path,
                bucket, 
                f"{output_key}/{get_filename(output_image_local_path)}"
            )
            for output_image_local_path in media_object["output_images_local_paths"]
        ]
        
        if any(media_object["output_images_s3_paths"]):
            media_object["images_uploaded"] = True
        
    return media_object

def check_for_failure(media_object):
    media_object["processing_successful"] = False
    
    conditions = [
        media_object["local_paths_exist"],
        media_object["article_available"],
        media_object["source_images_available"],
        media_object["output_images_available"],
        media_object["images_uploaded"]
    ]
    
    if all(conditions):
        media_object["processing_successful"] = True
    return media_object

def update_metadata(media_object):
    media_object["metadata_updated"] = False
    
    attribute_updates = {
        "ImagesURLs": {
            "Value": media_object["images_urls"]
        },
        "PostProducedImagesS3Paths":{
            "Value": "FAILED"
        }
    }
    
    if media_object["processing_successful"]:
        attribute_updates["PostProducedImagesS3Paths"]["Value"] = media_object["output_images_s3_paths"]
    
    asset_id = media_object["media_document_id"]
    
    try:
        dynamo_response = polly_metadata_store.update_item(
            Key={"AssetId": asset_id},
            AttributeUpdates=attribute_updates,
            ReturnValues="ALL_NEW"
        )
        media_object["metadata"] = dynamo_response
        media_object["metadata_updated"] = True
    except ClientError as e:
        print(e)
    
    return media_object

def trigger_video_pipeline(media_object):
    
    media_object['video_pipeline_triggered'] = False
    
    if media_object["metadata_updated"]:
    
        output_file = {
            "Bucket": media_object['s3_bucket'],
            "Key": media_object['video_trigger_s3_key'],
            "AssetId": media_object['media_document_id'],
            "ArticleBody": media_object['article_body'],
            "Metadata": media_object['metadata']['Attributes']
        }
        
        with open(media_object["video_trigger_local_path"], "w") as fp:
            json.dump(output_file, fp, default=default)
        
        try:
            s3.upload_file(
                media_object['video_trigger_local_path'],
                media_object['s3_bucket'],
                media_object['video_trigger_s3_key']
            )
            
            media_object['video_pipeline_triggered'] = True
            
        except ClientError as e:
            print(e)
            return None
        
    return media_object

def is_successful_ops(media_object):
    if media_object["processing_successful"] and media_object["metadata_updated"] and media_object["video_pipeline_triggered"]:
        return media_object
    return None

def is_failed_ops(media_object):
    if not media_object["processing_successful"] or not media_object["metadata_updated"] or not media_object["video_pipeline_triggered"]:
        return media_object
    return None

    
    

def handler(event, context):
    
    # input key: /audio/preview/$DOCUMENT_ID/$POLLY_GENERATED.wav
    
    Records = event["Records"]
    # assuming all objects are coming from the same bucket
    bucket = Records[0]["s3"]["bucket"]["name"]
    
    # [ "bucket_name", "audio/preview/$DOCUMENT_ID/$POLLY_GENERATED.wav" ]
    object_pairs = [ 
        [ bucket, x["s3"]["object"]["key"] ]
        for x in Records 
    ]
    
    media_objects = [ create_media_object(pair) for pair in object_pairs]
    
    local_paths = [ create_local_paths(media_object) for media_object in media_objects]
    
    articles = [download_article_object(local_path) for local_path in local_paths]
    
    images = [download_images(article) for article in articles]
    
    targas = [convert_images(image) for image in images]
    
    uploads = [ upload(targa) for targa in targas]
    
    checks = [ check_for_failure(upload) for upload in uploads]
    
    updates = [ update_metadata(check) for check in checks]
    
    trigger_videos = [trigger_video_pipeline(update) for update in updates]
    
    print(trigger_videos)
    
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

    