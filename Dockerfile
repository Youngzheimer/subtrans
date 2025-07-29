# Base image
FROM python:3.10-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set python to unbuffered mode
ENV PYTHONUNBUFFERED=1

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create config directory for persistent storage
RUN mkdir -p /app/config

# Create templates directory
RUN mkdir -p /app/templates

# Copy all Python modules
COPY *.py .

# Expose port for web UI
EXPOSE 8080

# Command to run both web UI and main process
CMD ["python", "start.py"]
