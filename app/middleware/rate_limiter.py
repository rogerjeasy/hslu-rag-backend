"""
Rate limiting middleware for the HSLU RAG Application API.
This limits how many requests a client can make in a given time period.
"""

from fastapi import Request, Response
import time
from typing import Dict, Tuple, List, Set
import logging
from app.core.exceptions import RateLimitException

logger = logging.getLogger("app.middleware.rate_limiter")

class RateLimiter:
    """
    Simple in-memory rate limiter that tracks IP addresses.
    
    For production, consider using Redis for distributed rate limiting.
    """
    
    def __init__(
        self, 
        rate_limit: int = 100, 
        window_seconds: int = 60,
        exclude_paths: Set[str] = None
    ):
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or {"/api/health", "/api/health/detailed"}
        self.requests: Dict[str, List[float]] = {}
        
        logger.info(
            f"Rate limiter initialized with {rate_limit} requests per {window_seconds} seconds"
        )
        
    async def __call__(self, request: Request, call_next):
        """Middleware implementation for rate limiting"""
        
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
            
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check if client has exceeded rate limit
        allow_request, retry_after = self._check_rate_limit(client_ip)
        
        if not allow_request:
            logger.warning(f"Rate limit exceeded for client IP: {client_ip}")
            raise RateLimitException(
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds."
            )
            
        # Process the request
        response = await call_next(request)
        
        # Add rate limit headers to response
        remaining, reset_time = self._get_rate_limit_status(client_ip)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _check_rate_limit(self, client_ip: str) -> Tuple[bool, int]:
        """
        Check if client has exceeded rate limit
        
        Returns:
            Tuple of (allow_request, retry_after_seconds)
        """
        current_time = time.time()
        
        # Initialize if client has no prior requests
        if client_ip not in self.requests:
            self.requests[client_ip] = []
            
        # Clean up old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < self.window_seconds
        ]
        
        # Check if rate limit exceeded
        if len(self.requests[client_ip]) >= self.rate_limit:
            # Calculate seconds until oldest request expires
            oldest_request = min(self.requests[client_ip])
            retry_after = int(self.window_seconds - (current_time - oldest_request))
            return False, retry_after
            
        # Add current request and allow it
        self.requests[client_ip].append(current_time)
        return True, 0
    
    def _get_rate_limit_status(self, client_ip: str) -> Tuple[int, int]:
        """
        Get status of rate limit for client
        
        Returns:
            Tuple of (remaining_requests, reset_time_seconds)
        """
        current_time = time.time()
        
        if client_ip not in self.requests:
            return self.rate_limit, self.window_seconds
            
        # Find remaining requests
        remaining = max(0, self.rate_limit - len(self.requests[client_ip]))
        
        # Calculate reset time (when oldest request expires)
        if self.requests[client_ip]:
            oldest_request = min(self.requests[client_ip])
            reset_time = int(self.window_seconds - (current_time - oldest_request))
        else:
            reset_time = self.window_seconds
            
        return remaining, reset_time