"""
HSLU RAG Application API Server
Main application entry point for the HSLU MSc Students' exam preparation assistant.
This API provides access to the Retrieval Augmented Generation (RAG) system that helps
students with course-specific questions, study guides, and practice materials.
"""

import os
import time
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Union

from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi

# Import application modules
from app.api.routes import auth, courses, materials, queries, study_guides, practice
from app.core.config import settings
from app.core.exceptions import BaseAPIException, AuthenticationException, PermissionDeniedException, NotFoundException, ValidationException, RateLimitException
# Not needed anymore as we're using uuid directly
# from app.core import security
# Application version and metadata
__version__ = "1.0.0"
API_PREFIX = "/api"

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.ENV.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("app.main")

# Lifecycle management for application startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle events.
    
    This context manager handles startup and shutdown events, including:
    - Database connections
    - Vector store initialization
    - Model loading
    - Resource cleanup
    """
    # Startup operations
    logger.info(f"Starting HSLU RAG API v{__version__} in {settings.ENV} environment")
    
    # Initialize connections to databases, vector stores, etc.
    # This could include database connections, loading models, etc.
    start_time = time.time()
    
    # TODO: Add initialization code here
    # await initialize_database()
    # await initialize_vector_store()
    # await initialize_models()
    
    logger.info(f"Application initialization completed in {time.time() - start_time:.2f} seconds")
    
    yield  # Server is running and processing requests
    
    # Shutdown operations
    logger.info("Application shutdown initiated")
    
    # Close connections, release resources
    # TODO: Add cleanup code here
    # await close_database_connections()
    # await release_model_resources()
    
    logger.info("Application shutdown completed")

# Create FastAPI application with custom metadata
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
# HSLU Data Science Exam Preparation API
    
This API powers the RAG (Retrieval Augmented Generation) system for HSLU MSc students in Applied Information and Data Science.
    
## Features
    
- **Course-Specific Question Answering**: Get answers based on your course materials
- **Exam Preparation**: Generate study guides and summaries
- **Practice Questions**: Test your knowledge with auto-generated questions
- **Concept Clarification**: Understand complex data science concepts
    
## Authentication
    
This API uses JWT Bearer tokens for authentication. Students need to authenticate with their HSLU credentials.
    
## Rate Limiting
    
Please note that this API implements rate limiting to ensure fair usage across all students.
    """,
    version=__version__,
    # Set these to None to prevent conflicts with our custom endpoints
    docs_url=None,  
    redoc_url=None,
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Serve static files (for API documentation, etc.)
static_dir = os.path.join(os.getcwd(), "static")
if os.path.exists(static_dir):
    logger.info(f"Mounting static files directory: {static_dir}")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logger.warning(f"Static directory '{static_dir}' doesn't exist. Documentation styling may be limited.")

# Custom documentation endpoints
@app.get(f"{API_PREFIX}/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Serve customized Swagger UI documentation"""
    swagger_js = "/static/swagger-ui-bundle.js"
    swagger_css = "/static/swagger-ui.css"
    favicon = "/static/favicon.png"
    
    return get_swagger_ui_html(
        openapi_url=f"{API_PREFIX}/openapi.json",
        title=f"{settings.PROJECT_NAME} - API Documentation",
        swagger_js_url=swagger_js,
        swagger_css_url=swagger_css,
        swagger_favicon_url=favicon,
    )

@app.get(f"{API_PREFIX}/redoc", include_in_schema=False)
async def redoc_html():
    """Serve ReDoc documentation"""
    from fastapi.openapi.docs import get_redoc_html
    
    redoc_js = "/static/redoc.standalone.js"
    favicon = "/static/favicon.png"
    
    return get_redoc_html(
        openapi_url=f"{API_PREFIX}/openapi.json",
        title=f"{settings.PROJECT_NAME} - ReDoc",
        redoc_js_url=redoc_js,
        redoc_favicon_url=favicon,
    )

# Create the redirect for documentation at root docs url
@app.get("/docs", include_in_schema=False)
async def docs_redirect():
    """Redirect /docs to /api/docs"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{API_PREFIX}/docs")

@app.get("/redoc", include_in_schema=False)
async def redoc_redirect():
    """Redirect /redoc to /api/redoc"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{API_PREFIX}/redoc")

# Security and monitoring middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    # Special handling for OPTIONS requests (preflight)
    if request.method == "OPTIONS":
        # For preflight requests, respond immediately with a 200 OK
        response = JSONResponse(content={}, status_code=200)
        
        # Add required CORS headers
        origin = request.headers.get("Origin", "")
        if origin in settings.CORS_ORIGINS or any(origin.endswith(domain.replace("*", "")) for domain in settings.CORS_ORIGINS if "*" in domain):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, Origin, User-Agent, DNT, Cache-Control, X-Requested-With"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "600"
        
        return response
    
    # For non-OPTIONS requests, proceed as normal
    protocol = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    is_https = protocol == "https"
    
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Only add HSTS header if we're on HTTPS
    if is_https:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Add CDN domains to CSP if needed
    cdn_domains = "cdn.jsdelivr.net"
    
    # Relaxed CSP that allows Swagger UI and ReDoc to function properly
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://{cdn_domains}; "
        f"style-src 'self' 'unsafe-inline' https://{cdn_domains}; "
        f"img-src 'self' data:; "
        f"font-src 'self' data: https://{cdn_domains}; "
        f"connect-src 'self' https://*.onrender.com http://localhost:3000 http://127.0.0.1:3000; "
        f"worker-src 'self' blob:; "
        f"child-src 'self' blob:; "
        f"frame-src 'self'"
    )
    
    return response

@app.middleware("http")
async def request_monitor(request: Request, call_next):
    """Log and monitor request information"""
    # Generate a unique request ID for tracking
    request_id = str(uuid.uuid4())
    request_path = request.url.path
    request_scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    request_method = request.method
    
    # Add request ID to request state for tracking
    request.state.request_id = request_id
    
    # Skip detailed logging for health check endpoints to reduce noise
    is_health_check = request_path.endswith("/health")
    
    if not is_health_check:
        logger.info(f"Request started: {request_method} {request_scheme}://{request.headers.get('host', '')}{request_path} (ID: {request_id})")
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        if not is_health_check:
            logger.info(
                f"Request completed: {request_method} {request_scheme}://{request.headers.get('host', '')}{request_path} "
                f"(ID: {request_id}) - Status: {response.status_code} - Time: {process_time:.4f}s"
            )
        
        return response
    
    except Exception as e:
        logger.exception(
            f"Request failed: {request_method} {request_scheme}://{request.headers.get('host', '')}{request_path} "
            f"(ID: {request_id}) - Error: {str(e)}"
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "request_id": request_id}
        )

# CORS middleware with more specific configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Authorization", "Content-Type", "Accept", "Origin", 
        "User-Agent", "DNT", "Cache-Control", "X-Requested-With",
        "X-Requested-For", "X-Forwarded-For", "X-Forwarded-Proto", "X-Forwarded-Host"
    ],
    expose_headers=["X-Request-ID", "X-Process-Time"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Include API routes with versioned prefix
app.include_router(auth, prefix=f"{API_PREFIX}/v1", tags=["Authentication"])
app.include_router(courses, prefix=f"{API_PREFIX}/v1", tags=["Courses"])
app.include_router(materials, prefix=f"{API_PREFIX}/v1", tags=["Course Materials"])
app.include_router(queries, prefix=f"{API_PREFIX}/v1", tags=["Queries"])
app.include_router(study_guides, prefix=f"{API_PREFIX}/v1", tags=["Study Guides"])
app.include_router(practice, prefix=f"{API_PREFIX}/v1", tags=["Practice Questions"])

# Serve static files (for API documentation, etc.)
try:
    static_dir = "static"  # Use your existing static folder
    if not os.path.exists(static_dir):
        logger.warning(f"Static directory '{static_dir}' doesn't exist. Creating it...")
        os.makedirs(static_dir)
        logger.info(f"Created directory: {static_dir}")
    
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Mounted static files directory: {static_dir}")
except Exception as e:
    logger.warning(f"Could not mount static files directory: {e}. Documentation may have limited styling.")

# Custom OpenAPI schema generation
def custom_openapi():
    """Generate a custom OpenAPI schema with additional information"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add OpenAPI version - this is required for Swagger UI to work properly
    openapi_schema["openapi"] = "3.0.2"
    
    # Add security schemes
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
        
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token in the format: Bearer {token}"
        }
    }
    
    # Add contact information
    openapi_schema["info"]["contact"] = {
        "name": "HSLU Data Science Support",
        "url": "https://www.hslu.ch/datascience-support",
        "email": "rogerjeasy@gmail.com"
    }
    
    # Add terms of service, license info
    openapi_schema["info"]["termsOfService"] = "https://www.hslu.ch/terms"
    openapi_schema["info"]["license"] = {
        "name": "HSLU License",
        "url": "https://www.hslu.ch/license"
    }
    
    # Add servers information for different environments
    server_url = settings.API_URL
    if server_url.startswith("http://localhost") and settings.ENV == "production":
        server_url = "https://hslu-rag-backend.onrender.com"
    
    environment = settings.ENV.capitalize()
    
    # Log the server URL being set in OpenAPI schema
    logger.info(f"Setting OpenAPI server URL to: {server_url}")
    
    openapi_schema["servers"] = [
        {"url": server_url, "description": f"{environment} Environment"}
    ]
    
    
    # Add tags with descriptions
    openapi_schema["tags"] = [
        {"name": "Authentication", "description": "User authentication and authorization operations"},
        {"name": "Courses", "description": "Course information and structure"},
        {"name": "Course Materials", "description": "Lecture materials, assignments, and resources"},
        {"name": "Queries", "description": "Question answering with the RAG system"},
        {"name": "Study Guides", "description": "Generate and manage study guides"},
        {"name": "Practice Questions", "description": "Generate and answer practice questions"},
        {"name": "Health", "description": "API health check endpoints"}
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Custom documentation endpoints
@app.get(f"{API_PREFIX}/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Serve customized Swagger UI documentation"""
    return get_swagger_ui_html(
        openapi_url=f"{API_PREFIX}/openapi.json",
        title=f"{settings.PROJECT_NAME} - API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.18.3/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.18.3/swagger-ui.css",
        oauth2_redirect_url=f"{API_PREFIX}/docs/oauth2-redirect",
    )

@app.get(f"{API_PREFIX}/redoc", include_in_schema=False)
async def redoc_html():
    """Serve ReDoc documentation"""
    from fastapi.openapi.docs import get_redoc_html
    
    return get_redoc_html(
        openapi_url=f"{API_PREFIX}/openapi.json",
        title=f"{settings.PROJECT_NAME} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )

# Global exception handler
@app.exception_handler(BaseAPIException)
async def base_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    logger.warning(
        f"API Exception: {exc.detail} - Code: {exc.status_code} - "
        f"Request: {request.method} {request.url.path} - ID: {getattr(request.state, 'request_id', 'unknown')}"
    )
    
    error_code = None
    if isinstance(exc, AuthenticationException):
        error_code = "auth_error"
    elif isinstance(exc, PermissionDeniedException):
        error_code = "permission_denied"
    elif isinstance(exc, NotFoundException):
        error_code = "not_found"
    elif isinstance(exc, ValidationException):
        error_code = "validation_error"
    elif isinstance(exc, RateLimitException):
        error_code = "rate_limit_exceeded"
    else:
        error_code = "internal_error"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": error_code,
            "request_id": getattr(request.state, 'request_id', 'unknown'),
        },
    )

# Health check endpoints for monitoring
@app.get(f"{API_PREFIX}/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint for uptime monitoring"""
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.ENV,
        "timestamp": int(time.time()),
        "api_url": settings.API_URL 
    }

@app.get(f"{API_PREFIX}/health/detailed", tags=["Health"])
async def detailed_health_check():
    """Detailed health check with component status information"""
    # TODO: Implement actual health checks for each component
    components = {
        "database": "ok",
        "vector_store": "ok",
        "llm_service": "ok",
        "embedding_service": "ok",
    }
    
    # Determine overall status
    overall_status = "ok" if all(v == "ok" for v in components.values()) else "degraded"
    
    return {
        "status": overall_status,
        "version": __version__,
        "environment": settings.ENV,
        "timestamp": int(time.time()),
        "components": components,
        "api_url": settings.API_URL 
    }

# Root endpoint with API information
@app.get("/", tags=["Root"])
async def root(request: Request):
    """API root with information and documentation links"""
    # Get the base URL dynamically from the request
    base_url = str(request.base_url).rstrip('/')
    
    # For production use, prefer the configured API_URL
    if settings.ENV == "production":
        base_url = "https://hslu-rag-backend.onrender.com"
    
    return {
        "name": settings.PROJECT_NAME,
        "version": __version__,
        "description": "RAG Application for HSLU MSc Students in Applied Information and Data Science",
        "documentation": f"{base_url}{API_PREFIX}/docs",
        "redoc": f"{base_url}{API_PREFIX}/redoc",
        "openapi": f"{base_url}{API_PREFIX}/openapi.json",
        "health": f"{base_url}{API_PREFIX}/health",
        "environment": settings.ENV,
    }

# Run the application using uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 8000))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()
    
    # Get number of workers (default to 1 if not specified)
    workers = getattr(settings, "WORKERS", 1)
    
    logger.info(f"Starting uvicorn server on port {port} with {workers} workers")
    
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=port, 
        log_level=log_level,
        reload=settings.ENV == "development",
        workers=workers,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )