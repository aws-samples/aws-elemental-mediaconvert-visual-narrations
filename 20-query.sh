#!/bin/bash

METADATA_ASSET_STORE=$(jq '.PollyPreviewSimpleStack.MetadataStoreName' stack.out/cdk-outputs.json | xargs)
ASSET_ID=$(jq '.AssetId' stack.out/article.json)

aws dynamodb get-item \
    --table-name $METADATA_ASSET_STORE \
    --key "{\"AssetId\":{\"S\":$ASSET_ID}}" \
    --output json > stack.out/processed-article.json