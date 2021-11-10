#!/bin/bash

export NVM_DIR=$HOME/.nvm
source $NVM_DIR/nvm.sh

download_ffmpeg(){
    echo "Downloading and installing FFmpeg and FFprobe."
    DEFAULT_PATH='functions/postprod-lambda/bin'
    DEST_PATH=${1:-$DEFAULT_PATH}
    FFMPEG_URL='https://github.com/giusedroid/ffmpeg-lgpl-amazonlinux2-no-network/raw/main/bin/ffmpeg?raw=true'
    FFPROBE_URL='https://github.com/giusedroid/ffmpeg-lgpl-amazonlinux2-no-network/raw/main/bin/ffprobe?raw=true'    
    mkdir -p $DEST_PATH
    curl -sL $FFMPEG_URL > $DEST_PATH/ffmpeg
    curl -sL $FFPROBE_URL > $DEST_PATH/ffprobe
    chmod +x $DEST_PATH/ffmpeg
    chmod +x $DEST_PATH/ffprobe
    
    echo "FFmpeg has been downloaded. Please review its license before proceeding."
    $DEST_PATH/ffmpeg -L
    
    echo "###################### IMPORTANT LEGAL NOTICE ######################"
    echo "this solution uses FFmpeg to analyze and manipulate the low-level visual and audio features of the uploaded media files."
    echo "FFmpeg (https://ffmpeg.org/) is a free and open-source software suite for handling video, audio, and other multimedia files and streams."
    echo "FFmpeg is distributed under the LGPL license (https://www.gnu.org/licenses/lgpl-2.1.en.html)."
    echo "For more information about FFmpeg, please see the following link: https://www.ffmpeg.org/."
    echo "Please carefully review the license prompted above before continuing."
    echo "Your use of the solution will cause you to use FFmpeg. If you do not want use of FFmpeg, do not use the solution."
    read -p "Do you wish to continue? (Y/N): " confirm && [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]] || exit 1
}

mkdir -p stack.out

echo "Installing JQ"
sudo yum install -y jq

download_ffmpeg

echo "OK, deploying the solution to your AWS account."

nvm install 14.17.6

cd functions/scrape-lambda
nvm use
npm i
cd ../..

nvm use
npm i
npx cdk bootstrap
npx cdk synth
npx cdk deploy --outputs-file ./stack.out/cdk-outputs.json