from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.utils.logging_config import setup_logging
from app.api.routes import router

# Setup logging
logger = setup_logging()

# Create FastAPI app
app = FastAPI(
    title="File Concatenator",
    description="A service to concatenate and analyze files from GitHub repositories",
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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting File Concatenator service")
    uvicorn.run(app, host="0.0.0.0", port=8000)
