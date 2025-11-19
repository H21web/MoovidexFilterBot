FROM python:3.10.8-slim-buster

# Install system dependencies including ffmpeg
RUN apt update && apt upgrade -y && \
    apt install -y git ffmpeg && \
    apt clean

# Copy requirements and install Python dependencies
COPY requirements.txt /requirements.txt
RUN pip3 install -U pip && pip3 install -U -r /requirements.txt

# Create app directory and set it as working dir
RUN mkdir /VJ-FILTER-BOT
WORKDIR /VJ-FILTER-BOT

# Copy all project files
COPY . /VJ-FILTER-BOT

# Run the bot
CMD ["python", "bot.py"]
