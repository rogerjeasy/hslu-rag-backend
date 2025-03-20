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
    curl \
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

# Make server.py executable
RUN chmod +x server.py

# Add debugging info
RUN echo "Development image ready"

# Run the application with auto-reload
CMD [ "sh", "-c", "echo 'Starting development server on port ${PORT:-8000}' && python server.py" ]

# For production stage
FROM base as production

# Copy the application
COPY . .

# Make server.py executable
RUN chmod +x server.py

# Add debugging info
RUN echo "Contents of /app:" && ls -la /app

# Simple health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Add debugging info
RUN echo "Production image ready"

# Run the application 
CMD [ "sh", "-c", "echo 'Starting production server on port ${PORT:-8000}' && exec python server.py" ]