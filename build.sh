#!/usr/bin/env bash
# Download and install FFmpeg
mkdir -p bin
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar xJ
mv ffmpeg-*-static/ffmpeg ffmpeg-*-static/ffprobe ./bin
chmod +x ./bin/ffmpeg ./bin/ffprobe
