"""
OnMemOS v3 Public SDK Server Application
User-facing endpoints for SDK clients
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.logging import setup_logging
from .core.config import load_settings
from .api import sessions as sessions_api
from .api import storage as storage_api
from .database.factory import get_database_client_async

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load settings
settings = load_settings()

# Create FastAPI app for public SDK
app = FastAPI(
    title="OnMemOS v3 Public API",
    description="User-facing endpoints for SDK clients",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for public access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include public routers
app.include_router(sessions_api.router)
app.include_router(storage_api.router)

@app.on_event("startup")
async def startup_event():
    """Initialize database connection"""
    try:
        db = await get_database_client_async()
        await db.connect()
        logger.info("✅ Public server database connected")
    except Exception as e:
        logger.error(f"❌ Public server database connection failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        db = await get_database_client_async()
        await db.disconnect()
        logger.info("✅ Public server database disconnected")
    except Exception as e:
        logger.error(f"❌ Public server shutdown error: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint for public server"""
    return {"status": "healthy", "server": "public", "version": "3.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app_public:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        reload=True
    )
