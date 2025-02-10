from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import pathlib
import logging
from typing import Dict, Any

from app.core.concatenator import FileConcatenator
from app.core.github_handler import GitHubHandler
from app.models.schemas import (
    ConcatenateRequest,
    FileConcatenatorError,
    FileConcatenationError,
    GitHubError,
    RepositoryNotFoundError,
    InvalidRepositoryError,
    AuthenticationError,
    RateLimitError,
    FileSystemError,
    CacheError,
    SubdirectoryError
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize GitHubHandler
github_handler = GitHubHandler(
    cache_dir=os.getenv("CACHE_DIR"),
    github_token=os.getenv("GITHUB_TOKEN"),
    cache_ttl=int(os.getenv("CACHE_TTL_HOURS", "1"))
)

# Add this function to initialize the handler when the application starts
@router.on_event("startup")
async def startup_event():
    await github_handler.initialize()

def create_error_response(error: Exception) -> Dict[str, Any]:
    """Create a standardized error response with enhanced details."""
    if isinstance(error, FileConcatenatorError):
        return error.to_dict()
    return {
        "status": "error",
        "message": str(error),
        "error_type": "UnexpectedError",
        "status_code": 500,
        "details": {
            "error_class": error.__class__.__name__,
            "help": "An unexpected error occurred. Please try again or contact support if the issue persists."
        }
    }

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/concatenate")
async def concatenate_files(request: ConcatenateRequest):
    """Concatenate files from a GitHub repository."""
    try:
        # Clean up the repository URL - convert HttpUrl to string first
        repo_url = str(request.repo_url).strip()
        
        # Clone the repository using the cached handler
        try:
            repo_path, subdir = await github_handler.clone_repository(
                repo_url=repo_url,
                github_token=request.github_token
            )
        except InvalidRepositoryError as e:
            if "tree" in repo_url:
                e.details["suggestion"] = "The URL appears to be from the GitHub web interface. You can use either this URL or the repository's root URL."
            raise e
        except AuthenticationError as e:
            if "private" in str(e).lower():
                e.details["suggestion"] = "This appears to be a private repository. Please provide a GitHub token with appropriate access."
            raise e
        
        # If a subdirectory was specified, use that as the base directory
        base_dir = repo_path
        if subdir:
            base_dir = repo_path / subdir
            if not base_dir.exists():
                raise SubdirectoryError(
                    subdir=subdir,
                    repo_url=repo_url,
                    reason="Directory not found in repository"
                )
            if not any(base_dir.iterdir()):
                raise SubdirectoryError(
                    subdir=subdir,
                    repo_url=repo_url,
                    reason="Directory is empty"
                )
        
        # Create concatenator with the cloned repository path
        try:
            concatenator = FileConcatenator(
                base_dir=str(base_dir),
                additional_ignores=request.additional_ignores or []
            )
        except FileConcatenationError as e:
            if "Directory does not exist" in str(e):
                e.details = {
                    "path": str(base_dir),
                    "suggestion": "The specified directory was not found. Please verify the path and try again."
                }
            raise e
        
        # Concatenate files
        output_file = await concatenator.concatenate_files()
        
        # Enhance success response with additional details
        return {
            "status": "success",
            "message": "Files concatenated successfully",
            "output_file": output_file,
            "statistics": concatenator.stats,
            "details": {
                "repository_url": repo_url,
                "subdirectory": subdir,
                "base_directory": str(base_dir),
                "processed_files_count": concatenator.stats.file_stats.processed_files,
                "total_files_count": concatenator.stats.file_stats.total_files
            }
        }
        
    except (RepositoryNotFoundError, InvalidRepositoryError, 
            AuthenticationError, RateLimitError, SubdirectoryError) as e:
        # Handle GitHub-specific errors
        error_response = create_error_response(e)
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response
        )
        
    except (FileSystemError, CacheError) as e:
        # Handle filesystem and cache errors
        logger.error(f"System error during concatenation: {e}")
        error_response = create_error_response(e)
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response
        )
        
    except FileConcatenationError as e:
        # Handle concatenation-specific errors
        error_response = create_error_response(e)
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response
        )
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error during concatenation: {e}")
        error_response = create_error_response(e)
        raise HTTPException(
            status_code=500,
            detail=error_response
        )

@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Download a concatenated file."""
    try:
        # Ensure the file path is within the output directory
        output_dir = pathlib.Path(__file__).parent.parent.parent / "output"
        file_path = output_dir / file_path
        
        # Validate path is within output directory
        try:
            file_path.relative_to(output_dir)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "Invalid file path",
                    "error_type": "ValidationError",
                    "status_code": 400
                }
            )
        
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "message": "File not found",
                    "error_type": "NotFoundError",
                    "status_code": 404
                }
            )
        
        if not file_path.is_file():
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "Path is not a file",
                    "error_type": "ValidationError",
                    "status_code": 400
                }
            )
            
        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type="text/plain"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to serve file",
                "error_type": "ServerError",
                "status_code": 500
            }
        ) 