import os
import json
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, validator, root_validator

RENDER_SECRET_PATH = "/etc/secrets/firebase-credentials.json"

class Settings(BaseSettings):
    # Project settings
    PROJECT_NAME: str = "HSLU AI Assistant RAG Application"
    API_V1_STR: str = "/api"
    
    # API URL for documentation and external references
    # In production, this will be set to the Render URL
    API_URL: str = "http://localhost:8000"
   
    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://hslu-exam-ai-assistant.vercel.app"]

    # Environment
    ENV: str = "development"
    WORKERS: int = 1
   
    # Firebase settings
    FIREBASE_CREDENTIALS: Optional[str] = None
    FIREBASE_WEB_API_KEY: str = ""
   
    # Vector database settings
    VECTOR_DB_TYPE: str = "chroma"  # Options: chroma, pinecone, weaviate
    VECTOR_DB_URL: str = ""
    VECTOR_DB_API_KEY: str = ""
    CHROMA_PERSIST_DIR: str = "./chroma_db"
   
    # LLM settings
    LLM_PROVIDER: str = "claude"  # Options: claude, gpt
    LLM_API_KEY: str = ""
   
    # Embedding settings
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 1536
   
    # Embedding provider settings
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL_NAME: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
   
    # Astra DB settings
    ASTRA_DB_API_ENDPOINT: str = ""
    ASTRA_DB_APPLICATION_TOKEN: str = ""
    ASTRA_DB_NAMESPACE: str = "default_keyspace"
    ASTRA_DB_COLLECTION: str = "hslu_rag_data"
   
    # OpenAI settings
    OPENAI_API_KEY: str = ""
   
    # Content processing settings
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
   
    # Performance and scaling
    MAX_CONCURRENT_REQUESTS: int = 100
    REQUEST_TIMEOUT: int = 60  # seconds
   
    # Cache settings
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # seconds
   
    # Root validator to handle Firebase credentials from file
    @root_validator(pre=True)
    def validate_firebase_credentials(cls, values):
        # Check if running on Render with mounted secret file
        if os.path.exists(RENDER_SECRET_PATH):
            try:
                with open(RENDER_SECRET_PATH, 'r') as f:
                    # Store the raw file content as a string
                    values["FIREBASE_CREDENTIALS"] = f.read()
            except Exception as e:
                print(f"Error reading Firebase credentials file: {e}")
        
        # If we're in test mode, we don't need to validate required fields
        if values.get("ENV") == "test":
            return values
            
        # Validate that we have Firebase credentials (either from file or env var)
        if not values.get("FIREBASE_CREDENTIALS"):
            raise ValueError("FIREBASE_CREDENTIALS must be provided")
            
        # Validate Astra DB settings
        if not values.get("ASTRA_DB_API_ENDPOINT"):
            raise ValueError("ASTRA_DB_API_ENDPOINT must be provided")
            
        if not values.get("ASTRA_DB_APPLICATION_TOKEN"):
            raise ValueError("ASTRA_DB_APPLICATION_TOKEN must be provided")
            
        return values
   
    @field_validator("EMBEDDING_PROVIDER")
    @classmethod
    def validate_embedding_provider(cls, v):
        if v not in ["openai", "huggingface"]:
            raise ValueError("EMBEDDING_PROVIDER must be 'openai' or 'huggingface'")
        return v
   
    @field_validator("EMBEDDING_MODEL_NAME")
    @classmethod
    def validate_embedding_model_name(cls, v):
        if not v:
            raise ValueError("EMBEDDING_MODEL_NAME must be provided")
        return v
   
    @field_validator("EMBEDDING_DIMENSIONS")
    @classmethod
    def validate_embedding_dimensions(cls, v):
        if not v:
            raise ValueError("EMBEDDING_DIMENSIONS must be provided")
        return v
    
    @field_validator("API_URL")
    @classmethod
    def validate_api_url(cls, v, values):
        # If we're in production, ensure API_URL doesn't use localhost
        env = values.data.get("ENV", "development")
        if env == "production" and "localhost" in v:
            # Default to the production URL if localhost is detected in production
            return "https://hslu-rag-backend.onrender.com"
        return v
       
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_file_encoding='utf-8',
        extra='ignore'
    )

# Helper method to get Firebase credentials as dict if needed
def get_firebase_creds_dict():
    # Check if running on Render with mounted secret file
    if os.path.exists(RENDER_SECRET_PATH):
        with open(RENDER_SECRET_PATH, 'r') as f:
            return json.load(f)
    else:
        # Fallback to environment variable
        creds = settings.FIREBASE_CREDENTIALS
        try:
            return json.loads(creds)
        except:
            return creds

# Initialize settings
settings = Settings()