"""
OnMemOS v3 Admin Server Application
Internal admin-only endpoints for UI management
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.logging import setup_logging
from .core.config import load_settings
from .api import admin as admin_api
from .api import gke as gke_api
from .database.factory import get_database_client_async

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load settings
settings = load_settings()

# Create FastAPI app for admin
app = FastAPI(
    title="OnMemOS v3 Admin API",
    description="Internal admin endpoints for UI management",
    version="3.0.0",
    docs_url="/admin/docs",
    redoc_url="/admin/redoc"
)

# CORS middleware for admin UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include admin-only routers
app.include_router(admin_api.router, prefix="/admin")
app.include_router(gke_api.router, prefix="/admin")  # GKE endpoints are admin-only

@app.on_event("startup")
async def startup_event():
    """Initialize database connection"""
    try:
        db = await get_database_client_async()
        await db.connect()
        logger.info("✅ Admin server database connected")
    except Exception as e:
        logger.error(f"❌ Admin server database connection failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        db = await get_database_client_async()
        await db.disconnect()
        logger.info("✅ Admin server database disconnected")
    except Exception as e:
        logger.error(f"❌ Admin server shutdown error: {e}")

@app.get("/admin/health")
async def health_check():
    """Health check endpoint for admin server"""
    return {"status": "healthy", "server": "admin", "version": "3.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.app_admin:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )
