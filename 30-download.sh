#!/bin/bash

PREVIEW_FILE=$(jq '.Item.PreviewVideoFile.S' stack.out/processed-article.json | xargs)

aws s3 cp $PREVIEW_FILE stack.out/preview.mp4