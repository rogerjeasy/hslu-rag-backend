from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import auth, courses, materials, queries, study_guides, practice
from app.core.config import settings
from app.core.exceptions import BaseAPIException

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

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)