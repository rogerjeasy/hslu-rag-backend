# app/api/deps.py
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user, check_admin_role, check_instructor_role, check_admin_or_instructor_role
from app.rag_new.rag_service import RAGService
from app.services.material_service import MaterialService
from app.services.llm_service import LLMService
from app.services.cloudinary_service import CloudinaryService

# Dependency functions to get services
def get_rag_service() -> RAGService:
    """Dependency for RAGService"""
    return RAGService()

def get_material_service() -> MaterialService:
    """Dependency for MaterialService"""
    return MaterialService()

def get_llm_service() -> LLMService:
    """Dependency for LLMService"""
    return LLMService()

def get_cloudinary_service() -> CloudinaryService:
    """Dependency for CloudinaryService"""
    return CloudinaryService()