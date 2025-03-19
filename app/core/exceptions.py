from fastapi import status


class BaseAPIException(Exception):
    """Base exception for API errors"""
    
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)


class AuthenticationException(BaseAPIException):
    """Exception for authentication errors"""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=status.HTTP_401_UNAUTHORIZED)


class PermissionDeniedException(BaseAPIException):
    """Exception for permission errors"""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=status.HTTP_403_FORBIDDEN)


class NotFoundException(BaseAPIException):
    """Exception for not found errors"""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=status.HTTP_404_NOT_FOUND)


class FirebaseException(BaseAPIException):
    """Exception for Firebase-related errors"""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RAGException(BaseAPIException):
    """Exception for RAG-related errors"""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidationException(BaseAPIException):
    """Exception for data validation errors"""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class RateLimitException(BaseAPIException):
    """Exception for rate limiting"""
    
    def __init__(self, detail: str = "Too many requests"):
        super().__init__(detail, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


class DocumentProcessingException(BaseAPIException):
    """Exception for document processing errors"""
    
    def __init__(self, detail: str):
        super().__init__(detail, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)