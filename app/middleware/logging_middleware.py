"""
@fileoverview
This middleware logs HTTP requests and responses for the application.
It captures request method, path, status code, processing time, and client IP.
"""

import time
import logging
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    
    Logs the following information for each request:
    - Request ID (UUID)
    - HTTP method
    - Path
    - Client IP
    - Status code
    - Processing time
    - User agent
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = logging.getLogger("api.request")
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Extract request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Log request start
        self.logger.info(
            f"Request {request_id} started: {method} {path} from {client_ip}"
        )
        
        # Measure processing time
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log successful response
            self.logger.info(
                f"Request {request_id} completed: {method} {path} - {response.status_code} "
                f"in {process_time:.4f}s - User-Agent: {user_agent}"
            )
            
            return response
            
        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log error
            self.logger.error(
                f"Request {request_id} failed: {method} {path} - Error: {str(e)} "
                f"in {process_time:.4f}s - User-Agent: {user_agent}"
            )
            
            # Re-raise the exception
            raise
