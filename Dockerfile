# Use Ubuntu as the base image
FROM ubuntu:22.04

# Set environment variables to prevent Python from writing .pyc files and to avoid buffering
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install system dependencies including Python, Java, and necessary libraries
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    openjdk-17-jre-headless \   
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

# Expose any ports your bot needs, e.g., 8080 (adjust as necessary for your bot)
EXPOSE 8080

# Command to run your bartender bot
CMD ["python3", "bartender-v2.py"]
