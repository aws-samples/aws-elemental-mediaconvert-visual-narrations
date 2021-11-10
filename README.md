# Social Media Stories and Visual Narrations with Amazon Polly and AWS Elemental MediaConvert

This project deploys a stack that ingests wordpress articles and produces two digital assets
- a full visual narration of variable length in which the article is read by Polly and the first four images 
- a Social Media story (30 seconds in duration) you can share on your favourite social media platform  

You can find more info about the stack on the [AWS Media Blog](insert-blog-article-url-here)  

## Deploying

1. Log to your AWS account
2. Deploy a Cloud 9 environment following [these instructions](https://docs.aws.amazon.com/cloud9/latest/user-guide/tutorial-create-environment.html)
3. Clone this repository on your Cloud9 Environment by running `git clone https://github.com/aws-samples/aws-elemental-mediaconvert-articles2video.git`
4. In a shell, run `./00-deploy.sh` and follow the instructions the script will prompt.

this will produce the file `stack.out/cdk-outputs.json`

**IMPORTANT LEGAL NOTICE**

This solution uses FFmpeg to analyze and manipulate the low-level visual and audio features of the uploaded media files.  
[FFmpeg](https://ffmpeg.org/) is a free and open-source software suite for handling video, audio, and other multimedia files and streams.  
FFmpeg is distributed under the [LGPL license v2.1](https://www.gnu.org/licenses/lgpl-2.1.en.html).  
For more information about FFmpeg, please see the following [here](https://www.ffmpeg.org/).  
Your use of the solution will cause you to use FFmpeg. If you do not want use of FFmpeg, do not use the solution.  

**IMPORTANT SECURITY NOTICE**
This solution makes use of FFmpeg compiled with `--disable-network` in order to prevent access to external resources. As this solution does not provide a mechanism to update FFmpeg, please make sure that you're updating version when needed.


## Testing

Once the deployment is completed, run `./10-test.sh` to start the workflow.  
The script will produce the file `stack.out/article.json` with the response from the API.  

## Getting Results

You can monitor the workflow by running `./20-query.sh`.  
This will produce the file `stack.out/processed-article.json`  
As the workflow may take a couple of minutes to produce all of the assets, please
run this script every 30 seconds until `PreviewVideoFile` and `FullVideoStream`
are populated.

## Downloading the Preview

Run this step once `PreviewVideoFile` is populated by `20-query.sh` in `stack.out/processed-article.json`.  
You can download the preview video file by running `./30-download.sh`.  
This will produce the file `stack.out/preview.mp4`

## Publishing the Full Narration
Run this step once `FullVideoStream` has been populated by `20-query.sh` in `stack.out/processed-article.json`.  

**WARNING:** by running the following step, you will be making a public copy of 
your full narration video asset.  

To publish your full narration, you can run `./40-publish.sh`: follow the instructions prompted
by the script.  
This step will copy your HLS playlist and segments and will make them public 
on the S3 Asset Store deployed by this code sample. Additionally, the script will 
generate and upload an HTML page on the S3 Asset Store.  
At the end of the process, the script will prompt a URL to the HTML page where you
can play the full narration.