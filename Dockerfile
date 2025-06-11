FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    postgresql-client \
    libpq-dev \
    curl \
    wget \
    git \
    python3-dev \
    libblas-dev \
    liblapack-dev \
    gfortran \
    pkg-config \
    libhdf5-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; \
    nltk.download('punkt', quiet=True); \
    nltk.download('vader_lexicon', quiet=True); \
    nltk.download('stopwords', quiet=True); \
    nltk.download('wordnet', quiet=True)" || true

# Create directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/models /app/static /app/templates /app/backups && \
    chmod 755 /app/logs /app/data /app/models /app/backups

# Copy application code
COPY . .

# Create non-root user and set permissions
RUN groupadd -r mktrading && \
    useradd -r -g mktrading -d /app -s /bin/bash mktrading && \
    chown -R mktrading:mktrading /app && \
    chmod +x /app

# Switch to non-root user
USER mktrading

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--worker-class", "sync", "--max-requests", "1000", "--max-requests-jitter", "100", "app:application"]
