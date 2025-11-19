# Use Debian 12 (Bookworm) or Debian 11 (Bullseye)
FROM python:3.9-bookworm
# OR
FROM python:3.9-bullseye

# Install system dependencies including ffmpeg
RUN apt update && apt upgrade -y && \
    apt install -y git ffmpeg && \
    apt clean



