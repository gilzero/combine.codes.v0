"""
@fileoverview
This is the main entry point for the Combine Codes application. It sets up
the FastAPI application, configures middleware, mounts static files, and includes
API routes. It also handles environment variable loading and logging configuration.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.utils.logging_config import setup_logging
from app.utils.error_handler import register_exception_handlers
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.api.routes import router
from contextlib import asynccontextmanager

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = setup_logging()
logger.info("Logging system initialized")

# Ensure Stripe API key is loaded
try:
    import stripe
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if stripe_key:
        stripe.api_key = stripe_key
        logger.info(f"Stripe API key loaded from environment (masked): {stripe_key[:4]}...{stripe_key[-4:]}")
    else:
        logger.warning("Stripe API key not found in environment variables")
except ImportError:
    logger.warning("Stripe module not installed")
except Exception as e:
    logger.error(f"Error loading Stripe API key: {str(e)}")

# Create FastAPI application
app = FastAPI(
    title="Combine Codes",
    description="A service to combine and analyze files from GitHub repositories",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Register exception handlers
register_exception_handlers(app)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Include API routes
app.include_router(router, prefix="")

# Create required directories
Path("output").mkdir(exist_ok=True)
Path("cache").mkdir(exist_ok=True)
Path("logs").mkdir(exist_ok=True)

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup actions
    logger.info("Starting Combine Codes service")
    logger.info(f"Environment: {os.getenv('ENV', 'development')}")
    logger.info(f"GitHub token configured: {'Yes' if os.getenv('GITHUB_TOKEN') else 'No'}")
    
    # Check Stripe configuration
    stripe_key = os.getenv('STRIPE_SECRET_KEY')
    stripe_key_masked = f"{stripe_key[:4]}...{stripe_key[-4:]}" if stripe_key and len(stripe_key) > 8 else None
    logger.info(f"Stripe configuration: {'Yes' if stripe_key else 'No'}")
    if stripe_key:
        logger.info(f"Stripe key (masked): {stripe_key_masked}")
        logger.info(f"Stripe key length: {len(stripe_key)}")
        
        # Ensure stripe module has the key
        import stripe
        if stripe.api_key != stripe_key:
            logger.warning(f"Stripe API key mismatch. Resetting to environment value.")
            stripe.api_key = stripe_key
    else:
        logger.warning("Stripe API key not found in environment variables")
    
    logger.info(f"Cache directory: {os.getenv('CACHE_DIR', 'cache')}")
    logger.info(f"Cache TTL: {os.getenv('CACHE_TTL', '3600')} seconds")
    
    yield  # This is where the application runs

    # Shutdown actions (if any)
    logger.info("Shutting down Combine Codes service")

# Assign the lifespan context manager to the app
app.lifespan = lifespan

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
