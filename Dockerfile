# Use Python 3.9 slim image (good choice for ML workloads)
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables early
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for your ML/trading project
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    postgresql-client \
    libpq-dev \
    curl \
    wget \
    git \
    # Required for NLTK and ML libraries
    python3-dev \
    # Required for numerical libraries
    libblas-dev \
    liblapack-dev \
    gfortran \
    # Required for web scraping (selenium if needed)
    chromium-driver \
    # Required for some Python packages
    pkg-config \
    libhdf5-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create necessary directories
RUN mkdir -p /app/logs \
    && mkdir -p /app/data \
    && mkdir -p /app/models \
    && mkdir -p /app/static \
    && mkdir -p /app/templates \
    && mkdir -p /app/backups

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Download NLTK data (required for sentiment analysis)
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('vader_lexicon'); nltk.download('stopwords'); nltk.download('wordnet')" || true

# Copy application code (do this after pip install for better caching)
COPY . .

# Create non-root user for security
RUN groupadd -r mktrading && useradd -r -g mktrading mktrading \
    && chown -R mktrading:mktrading /app

# Switch to non-root user
USER mktrading

# Expose port
EXPOSE 5000

# Add comprehensive health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || curl -f http://localhost:5000/test_db || exit 1

# Use gunicorn for production deployment instead of Flask dev server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--worker-class", "sync", "app:app"]