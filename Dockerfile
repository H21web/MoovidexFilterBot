# Python 3.12 on Debian bookworm (verified image tag)
FROM python:3.12-slim-bookworm

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y git ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Command to run the application
CMD ["python", "bot.py"]
