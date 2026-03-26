# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (e.g., cron)
RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the logs directory
RUN mkdir -p logs

# Expose the API port
EXPOSE 3215

# Set the entrypoint
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
