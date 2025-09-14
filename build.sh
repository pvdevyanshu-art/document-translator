#!/usr/bin/env bash
# exit on error
set -o errexit

echo "---> Installing Tesseract OCR Engine"
apt-get update
apt-get install -y tesseract-ocr libtesseract-dev

echo "---> Installing Python dependencies"
pip install -r requirements.txt