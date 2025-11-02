"""FastAPI application for Todo CLI web app."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import auth_router
from .middleware import AuthMiddleware
from .database import get_user_db
from .auth import get_auth_service


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.
    
    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting Todo CLI Web App")
    
    # Initialize database
    db = get_user_db()
    logger.info(f"Database initialized at {db.db_path}")
    
    # Initialize auth service
    auth_service = get_auth_service()
    logger.info("Authentication service initialized")
    
    # Cleanup expired sessions on startup
    cleaned = auth_service.cleanup_expired_sessions()
    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} expired sessions")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Todo CLI Web App")
    db.close()


# Create FastAPI application
app = FastAPI(
    title="Todo CLI Web App",
    description="Remote web interface for Todo CLI with real-time synchronization",
    version="0.1.0",
    lifespan=lifespan
)


# Configure CORS
# Note: In production, configure this with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add authentication middleware
app.middleware("http")(AuthMiddleware(app))


# Include routers
app.include_router(auth_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint.
    
    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "todo-cli-webapp",
        "version": "0.1.0"
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information.
    
    Returns:
        API information
    """
    return {
        "service": "Todo CLI Web App",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "api": {
            "auth": "/api/auth",
            "tasks": "/api/tasks (coming soon)",
            "projects": "/api/projects (coming soon)",
            "sync": "/ws/sync (coming soon)"
        }
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected exceptions.
    
    Args:
        request: FastAPI request
        exc: Exception
        
    Returns:
        Error response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "todo_cli.webapp.server.app:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
        log_level="info"
    )
