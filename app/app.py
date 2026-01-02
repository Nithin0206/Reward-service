import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers.reward_router import router
from app.routers.persona_mock_router import router as persona_mock_router
from app.middleware import (
    RequestIDMiddleware,
    TimingMiddleware,
    LoggingMiddleware,
    SecurityHeadersMiddleware,
    request_id_var
)
from app.cache.cache_manager import get_cache
from app.utils.config_loader import has_config_changed, reload_config


async def config_hot_reload_task():
    """
    Background task to check for config file changes and reload.
    Runs every 1 hour to detect changes in config.yaml.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # Checking for config changes every 1 hour
            if has_config_changed():
                print("Config file changed detected, reloading...")
                reload_config()
        except Exception as e:
            print(f"Error in config hot-reload task: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown.
    Replaces deprecated @app.on_event decorators.
    """
    # Startup: Initialize shared application state
    app.state.cache = await get_cache()
    print(f"Cache initialized: {type(app.state.cache).__name__}")
    
    # Start config hot-reload background task
    app.state.config_reload_task = asyncio.create_task(config_hot_reload_task())
    print("Config hot-reload enabled (checks every 1 hour)")
    
    yield  
    
    # Shutdown: Cleanup resources
    if hasattr(app.state, 'config_reload_task'):
        app.state.config_reload_task.cancel()
        try:
            await app.state.config_reload_task
        except asyncio.CancelledError:
            pass
    
    if hasattr(app.state, 'cache') and hasattr(app.state.cache, 'close'):
        await app.state.cache.close()
        print("Cache closed")


app = FastAPI(
    title="Reward Decision Service",
    description="Service for calculating and deciding rewards for transactions",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
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


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint with cache status."""
    cache_healthy = False
    if hasattr(app.state, 'cache'):
        try:
            cache_healthy = await app.state.cache.ping()
        except Exception:
            pass
    
    return {
        "status": "healthy" if cache_healthy else "degraded",
        "service": "Reward Decision Service",
        "cache": "connected" if cache_healthy else "disconnected",
        "hot_reload": "enabled"
    }


# Manual config reload endpoint
@app.post("/admin/reload-config")
async def manual_config_reload():
    """Manually trigger config reload."""
    try:
        new_config = reload_config()
        return {
            "status": "success",
            "message": "Configuration reloaded successfully",
            "policy_version": new_config.get("policy_version", "unknown")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to reload config: {str(e)}"
        }


# Include routers
app.include_router(router)
app.include_router(persona_mock_router)
