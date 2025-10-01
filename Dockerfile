# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set default UID and GID if not provided
ARG UID=1000
ARG GID=1000

# Switch to root user to install OS-level packages
USER root

# Install curl and other necessary packages
RUN apt-get update && apt-get install -y curl gnupg2 apt-transport-https

# For some DAG using DefaultAzureCredential()
# Add the Azure CLI software repository
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Set the working directory inside the container
WORKDIR /app

# Create the user and group with the provided or default IDs
RUN groupadd -g ${GID} david && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash david

# Ensure the user has the necessary permissions for any required directories
RUN mkdir -p /opt/airflow && chown -R david:david /opt/airflow

# Copy only requirements.txt to install dependencies first (optimization)
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app

# Switch to the non-root user
USER david

# Run app.py when the container launches
# Comment out the existing CMD to run the script immediately
# CMD ["python", "/app/python/app.py"]

# Use a simple idle command to keep the container running
# CMD ["tail", "-f", "/dev/null"]
