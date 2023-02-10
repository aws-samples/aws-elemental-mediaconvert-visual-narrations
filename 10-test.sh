#!/bin/bash

# Download templates if not exist
wget -nc https://github.com/giusedroid/aws-visual-narratives-templates/raw/main/assets/Template_video_right.mov -O template/Template_video_right.mov
wget -nc https://github.com/giusedroid/aws-visual-narratives-templates/raw/main/assets/template.mov -O template/template.mov

# Upload templates to bucket
S3_BUCKET=$(jq .'PollyPreviewSimpleStack.AssetStoreBucketName' stack.out/cdk-outputs.json | xargs)
aws s3 sync template s3://$S3_BUCKET/custom/template

# Invoke API
API_ENDPOINT=$(jq .'PollyPreviewSimpleStack.APIEndpoint' stack.out/cdk-outputs.json | xargs)

curl -X POST -H "Content-Type: application/json" \
    -d '{"Url": "https://giusedroid.wordpress.com/2021/04/29/a-brief-history-of-ferrari"}' \
    $API_ENDPOINT > stack.out/article.json
