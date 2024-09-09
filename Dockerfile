# Use an official Ubuntu image as the base
FROM ubuntu:22.04

# Set environment variables to prevent Python from writing .pyc files and to avoid buffering
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install system dependencies, including Python and other required tools
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    ffmpeg \
    portaudio19-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    wget \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python dependencies from requirements.txt
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

# Command to run the bartender bot
CMD ["python3", "bartender.py"]
