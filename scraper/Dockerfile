# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
        unzip \
        awscli \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m appuser
WORKDIR /home/appuser

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt && pip install boto3 python-dotenv loguru

# Copy the rest of the code
COPY . .

# Change ownership
RUN chown -R appuser:appuser /home/appuser
USER appuser

# Entrypoint (override in docker-compose or command line)
ENTRYPOINT ["python"]
CMD ["enhanced_100_percent_working.py"] 