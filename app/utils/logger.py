"""
Logger configuration module for the HSLU RAG application.

This module provides a standardized logging setup with structured log output,
configurable log levels, and proper formatting for both development and production.
"""

import logging
import sys
import json
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Union

from app.core.config import settings

class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in a structured JSON format.
    This is particularly useful for log aggregation systems like ELK.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "environment": settings.ENVIRONMENT,
            "service": settings.PROJECT_NAME,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add any extra context passed with the log
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
            
        # Include any extra fields
        for key, value in record.__dict__.items():
            if key.startswith('ctx_'):
                log_data[key[4:]] = value
                
        return json.dumps(log_data)

class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that allows attaching context to log records.
    This makes it easy to include request IDs and other context in logs.
    """
    
    def process(self, msg, kwargs):
        # Transfer context from adapter to log record
        kwargs.setdefault('extra', {})
        for key, value in self.extra.items():
            kwargs['extra'][key] = value
        return msg, kwargs

def setup_logging(
    log_level: Union[str, int] = "INFO", 
    enable_json_logs: Optional[bool] = None
) -> ContextAdapter:
    """
    Configure application logging.
    
    Args:
        log_level: The logging level to use
        enable_json_logs: Whether to output logs as JSON (default depends on environment)
        
    Returns:
        Configured logger
    """
    # Convert string log level to numeric if needed
    if isinstance(log_level, str):
        log_level = getattr(logging, log_level.upper())
    
    # Determine if JSON logging should be used (default to JSON in production)
    if enable_json_logs is None:
        enable_json_logs = settings.ENVIRONMENT != "development"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicate logs
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    
    # Create handler for stdout
    handler = logging.StreamHandler(sys.stdout)
    
    # Configure formatter based on environment
    if enable_json_logs:
        formatter = StructuredFormatter()
    else:
        # More readable format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Create application logger
    logger = logging.getLogger("app")
    logger.setLevel(log_level)
    
    # Wrap with context adapter
    return ContextAdapter(logger, {})

def get_logger(name: str, **context) -> ContextAdapter:
    """
    Get a logger with the given name and context.
    
    Args:
        name: Logger name
        context: Additional context to include in logs
        
    Returns:
        Logger with context
    """
    logger = logging.getLogger(name)
    return ContextAdapter(logger, context)