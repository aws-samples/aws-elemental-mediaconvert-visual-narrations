#!/bin/bash

API_ENDPOINT=$(jq .'PollyPreviewSimpleStack.APIEndpoint' stack.out/cdk-outputs.json | xargs)

curl -X POST -H "Content-Type: application/json" \
    -d '{"Url": "https://giusedroid.wordpress.com/2021/04/29/a-brief-history-of-ferrari/amp/"}' \
    $API_ENDPOINT > stack.out/article.json