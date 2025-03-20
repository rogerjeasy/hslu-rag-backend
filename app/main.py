from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
import sys
from app.api.routes import auth, courses, materials, queries, study_guides, practice
from app.core.config import settings
from app.core.exceptions import BaseAPIException

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("app.main")

# Log startup message
logger.info("Starting application...")
logger.info(f"Environment: {os.environ.get('ENV', 'development')}")
logger.info(f"PORT environment variable: {os.environ.get('PORT', 'not set')}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RAG Application for HSLU MSc Students in Applied Information and Data Science",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth, prefix="/api", tags=["Authentication"])
app.include_router(courses, prefix="/api", tags=["Courses"])
app.include_router(materials, prefix="/api", tags=["Course Materials"])
app.include_router(queries, prefix="/api", tags=["Queries"])
app.include_router(study_guides, prefix="/api", tags=["Study Guides"])
app.include_router(practice, prefix="/api", tags=["Practice Questions"])

# Global exception handler
@app.exception_handler(BaseAPIException)
async def base_exception_handler(request: Request, exc: BaseAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.on_event("startup")
async def startup_event():
    """Log when the application starts and is ready to receive requests"""
    port = os.environ.get("PORT", 8000)
    logger.info(f"Application started and listening on port {port}")
    logger.info(f"Visit the API documentation at: http://localhost:{port}/api/docs")

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint called")
    return {"status": "You're good to go!"}

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    logger.info("Root endpoint called")
    return {"message": "Welcome to the RAG API. Go to /api/docs for documentation."}

if __name__ == "__main__":
    import uvicorn
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting uvicorn server on port {port}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")