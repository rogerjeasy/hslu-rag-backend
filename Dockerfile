FROM python:3.12-slim as base

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies in a layer that can be cached
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install NLP models
RUN python -m spacy download en_core_web_sm

# For development stage
FROM base as development

# Install development tools
RUN pip install \
    black \
    isort \
    flake8 \
    mypy \
    pytest \
    pytest-asyncio \
    ipython

# Copy the rest of the application
COPY . .

# Run the application with auto-reload
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload

# For production stage
FROM base as production

# Copy the application
COPY . .

# Run the application
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4