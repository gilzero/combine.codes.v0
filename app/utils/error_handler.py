"""
@fileoverview
This module provides error handling utilities for the application.
It includes exception classes and handlers that ensure proper logging of errors.
"""

import logging
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Get logger
logger = logging.getLogger(__name__)

class AppException(Exception):
    """
    Base exception class for application-specific exceptions.
    
    Attributes:
        status_code: HTTP status code to return
        detail: Error message
        headers: Additional headers to include in the response
    """
    
    def __init__(self, status_code: int, detail: str, headers: dict = None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


class GitHubException(AppException):
    """Exception raised for GitHub API errors."""
    
    def __init__(self, detail: str, headers: dict = None):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail, headers=headers)


class StripeException(AppException):
    """Exception raised for Stripe API errors."""
    
    def __init__(self, detail: str, headers: dict = None):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail, headers=headers)


class FileProcessingException(AppException):
    """Exception raised for file processing errors."""
    
    def __init__(self, detail: str, headers: dict = None):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail, headers=headers)


async def app_exception_handler(request: Request, exc: AppException):
    """
    Handler for application-specific exceptions.
    
    Logs the exception and returns a JSON response with the error details.
    """
    logger.error(f"Application error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handler for HTTP exceptions.
    
    Logs the exception and returns a JSON response with the error details.
    """
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler for validation exceptions.
    
    Logs the exception and returns a JSON response with the validation error details.
    """
    error_detail = str(exc)
    logger.error(f"Validation error: {error_detail}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handler for unhandled exceptions.
    
    Logs the full exception traceback and returns a generic error response.
    """
    # Log the full traceback
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
