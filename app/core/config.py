import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    # Project settings
    PROJECT_NAME: str = "HSLU RAG Application"
    API_V1_STR: str = "/api"
   
    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://yourdomain.com"]
   
    # Firebase settings
    FIREBASE_CREDENTIALS: str = ""
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
    
    # Environment
    ENV: str = "development"
   
    @field_validator("FIREBASE_CREDENTIALS")
    @classmethod
    def validate_firebase_credentials(cls, v):
        if not v and os.environ.get("ENV") != "test":
            raise ValueError("FIREBASE_CREDENTIALS must be provided")
        return v
   
    @field_validator("ASTRA_DB_API_ENDPOINT")
    @classmethod
    def validate_astra_db_endpoint(cls, v):
        if not v and os.environ.get("ENV") != "test":
            raise ValueError("ASTRA_DB_API_ENDPOINT must be provided")
        return v
   
    @field_validator("ASTRA_DB_APPLICATION_TOKEN")
    @classmethod
    def validate_astra_db_token(cls, v):
        if not v and os.environ.get("ENV") != "test":
            raise ValueError("ASTRA_DB_APPLICATION_TOKEN must be provided")
        return v
   
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
       
    # Update Config to the new format used in pydantic_settings
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()