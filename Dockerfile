# Use Python 3.10 slim as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    DEVELOPMENT_MODE=false

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Copy project files
COPY . .

# Create necessary directories if they don't exist
RUN mkdir -p data
RUN chmod 777 data

# Run as non-root user for better security
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Run gunicorn server with correct syntax
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "3", "--threads", "3", "app:app"]