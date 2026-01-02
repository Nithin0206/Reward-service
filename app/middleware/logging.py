"""Logging middleware for request/response logging."""

from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request and response details."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Log request
        print(f"[{request_id}] {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
        
        try:
            response = await call_next(request)
            # Log response
            print(f"[{request_id}] Response: {response.status_code}")
            return response
        except Exception as e:
            print(f"[{request_id}] Error: {str(e)}")
            raise

