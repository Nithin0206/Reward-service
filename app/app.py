from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers.reward_router import router
from app.middleware import (
    RequestIDMiddleware,
    TimingMiddleware,
    LoggingMiddleware,
    SecurityHeadersMiddleware,
    request_id_var
)



app = FastAPI(
    title="Reward Decision Service",
    description="Service for calculating and deciding rewards for transactions",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"]
)

# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handling any unhandled exceptions globally."""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": request_id
        }
    )


# Include routers
app.include_router(router)
