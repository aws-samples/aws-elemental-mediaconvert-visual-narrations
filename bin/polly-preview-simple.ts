#!/usr/bin/env node
import * as cdk from '@aws-cdk/core';
import { PollyPreviewSimpleStack } from '../lib/polly-preview-simple-stack';

const app = new cdk.App();
new PollyPreviewSimpleStack(app, 'PollyPreviewSimpleStack');
