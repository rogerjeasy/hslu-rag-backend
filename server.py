#!/usr/bin/env python
import os
import logging
import sys
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("server")

# Get environment variables for configuration
PORT = int(os.environ.get("PORT", 8000))
WORKERS = int(os.environ.get("WEB_CONCURRENCY", 4))

logger.info(f"Starting server with PORT={PORT} and WORKERS={WORKERS}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Files in current directory: {os.listdir('.')}")
logger.info(f"Environment variables: PORT={os.environ.get('PORT')}")

if __name__ == "__main__":
    logger.info(f"Starting uvicorn server on 0.0.0.0:{PORT} with {WORKERS} workers")
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=PORT,
        workers=WORKERS, 
        log_level="info",
        access_log=True
    )