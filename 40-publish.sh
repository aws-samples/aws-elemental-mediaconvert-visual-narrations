#!/bin/bash
AWS_REGION=$(aws configure get region)
ASSET_STORE=$(jq '.PollyPreviewSimpleStack.AssetStoreBucketName' stack.out/cdk-outputs.json | xargs)
FULL_STREAM_M3U8=$(jq '.Item.FullVideoStream.S' stack.out/processed-article.json | xargs)
FULL_STREAM_PATH=${FULL_STREAM_M3U8%/*}
ASSET_ID=${FULL_STREAM_PATH##*/}
PUBLIC_PATH=s3://$ASSET_STORE/public/full/hls/$ASSET_ID

STREAM_URL=https://$ASSET_STORE.s3.$AWS_REGION.amazonaws.com/public/full/hls/$ASSET_ID/template.m3u8
INDEX_URL=https://$ASSET_STORE.s3.$AWS_REGION.amazonaws.com/public/full/hls/$ASSET_ID/index.html

echo "WARNING: By running this script, you will publish your HLS (video asset) to s3://$ASSET_STORE/public/full/hls"
read -p "Do you wish to continue? (Y/N): " confirm && [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]] || exit 1

aws s3 cp $FULL_STREAM_PATH/ $PUBLIC_PATH --acl public-read --recursive

rm stack.out/index.html
cp assets/player.template.html stack.out/index.html
sed -i "s@{STREAM_URL}@$STREAM_URL@g" stack.out/index.html

aws s3 cp stack.out/index.html $PUBLIC_PATH/ --acl public-read

aws s3 cp $FULL_STREAM_M3U8 stack.out/template.m3u8

echo "Website endpoint: $INDEX_URL"

