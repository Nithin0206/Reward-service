"""Request ID middleware for adding unique request IDs to each request."""

import uuid
from contextvars import ContextVar
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable for request ID (useful for logging and tracing)
request_id_var: ContextVar[str] = ContextVar('request_id', default='')


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add a unique request ID to each request."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

