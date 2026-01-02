"""Timing middleware for tracking request processing time."""

import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request processing time to response headers."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(round(process_time, 4))
        return response

