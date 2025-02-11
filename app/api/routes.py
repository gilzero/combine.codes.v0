from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import pathlib
import logging
from typing import Dict, Any
import asyncio

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
    SubdirectoryError,
    RepositoryPreCheckRequest,
    RepositoryPreCheckResponse,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    PaymentStatus,
    GitHubRepoInfo
)

import stripe

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Log GitHub token status
github_token = os.getenv("GITHUB_TOKEN")
logger.info(f"GitHub token loaded from environment: {'Yes' if github_token else 'No'}")
if github_token:
    logger.info(f"GitHub token length: {len(github_token)}")
    logger.info(f"GitHub token format: {'Valid' if github_token.startswith(('ghp_', 'github_pat_')) else 'Invalid'}")

# Initialize GitHubHandler
github_handler = GitHubHandler(
    cache_dir=os.getenv("CACHE_DIR"),
    github_token=github_token,
    cache_ttl=int(os.getenv("CACHE_TTL_HOURS", "1"))
)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
PRICE_USD = 0.50

# Store checkout sessions in memory (in production, use a proper database)
checkout_sessions: Dict[str, Dict[str, Any]] = {}

# Add this function to initialize the handler when the application starts
@router.on_event("startup")
async def startup_event():
    await github_handler.initialize()

# Add cleanup for aiohttp session
@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    if hasattr(github_handler, 'session'):
        await github_handler.session.close()

class ErrorHandler:
    """Centralized error handling for the API."""
    
    @staticmethod
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
    
    @staticmethod
    def handle_authentication_error(e: AuthenticationError) -> HTTPException:
        """Handle authentication-related errors."""
        logger.error(f"Authentication error during pre-check: {str(e)}")
        if "format" in str(e):
            return HTTPException(
                status_code=401,
                detail={
                    "message": str(e),
                    "error_type": "InvalidTokenFormat",
                    "requires_token": True
                }
            )
        elif "permissions" in str(e):
            return HTTPException(
                status_code=401,
                detail={
                    "message": "The provided GitHub token lacks required permissions",
                    "error_type": "InsufficientPermissions",
                    "requires_token": True
                }
            )
        return HTTPException(
            status_code=401,
            detail={
                "message": str(e),
                "error_type": "AuthenticationError",
                "requires_token": True
            }
        )
    
    @staticmethod
    def handle_rate_limit_error(e: RateLimitError) -> HTTPException:
        """Handle rate limit errors."""
        logger.error("Rate limit exceeded during pre-check")
        return HTTPException(
            status_code=429,
            detail={
                "message": "GitHub API rate limit exceeded. Please try again later or provide a GitHub token.",
                "error_type": "RateLimitExceeded",
                "requires_token": True
            }
        )
    
    @staticmethod
    def handle_repository_not_found(e: RepositoryNotFoundError, repo_url: str) -> HTTPException:
        """Handle repository not found errors."""
        logger.error(f"Repository not found: {str(e)}")
        return HTTPException(
            status_code=404,
            detail={
                "message": f"Repository not found: {repo_url}",
                "error_type": "RepositoryNotFound",
                "requires_token": True
            }
        )

# Initialize error handler
error_handler = ErrorHandler()

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stripe_publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY")
        }
    )

@router.post("/pre-check", response_model=RepositoryPreCheckResponse)
async def pre_check_repository(request: RepositoryPreCheckRequest):
    """Pre-check repository and create payment session."""
    try:
        logger.info(f"Received pre-check request for repository: {request.repo_url}")
        logger.debug(f"Request details - Token provided: {'yes' if request.github_token else 'no'}")
        
        # Get repository information
        try:
            repo_info = await github_handler.pre_check_repository(
                str(request.repo_url),
                request.github_token
            )
            logger.info(f"Successfully retrieved repository info for {repo_info.owner}/{repo_info.repo_name}")
            
        except AuthenticationError as e:
            raise error_handler.handle_authentication_error(e)
        except RateLimitError as e:
            raise error_handler.handle_rate_limit_error(e)
        except RepositoryNotFoundError as e:
            raise error_handler.handle_repository_not_found(e, request.repo_url)
            
        # Create Stripe checkout session
        try:
            checkout_session = await create_stripe_checkout_session(
                repo_info=repo_info,
                base_url=request.base_url
            )
            logger.info(f"Created Stripe checkout session: {checkout_session.id}")
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Failed to create payment session",
                    "error_type": "PaymentError"
                }
            )
        
        # Store session for verification
        checkout_sessions[checkout_session.id] = {
            'status': 'pending',
            'repo_url': str(request.repo_url),
            'github_token': request.github_token
        }
        
        response_data = RepositoryPreCheckResponse(
            repo_name=repo_info.repo_name,
            owner=repo_info.owner,
            estimated_file_count=repo_info.estimated_file_count,
            repository_size_kb=repo_info.size,
            price_usd=PRICE_USD,
            checkout_session_id=checkout_session.id
        )
        
        logger.info(f"Successfully completed pre-check for {repo_info.owner}/{repo_info.repo_name}")
        return response_data
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error in pre-check: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "An unexpected error occurred while checking the repository",
                "error_type": "UnexpectedError"
            }
        )

async def create_stripe_checkout_session(repo_info: GitHubRepoInfo, base_url: str) -> stripe.checkout.Session:
    """Create a Stripe checkout session."""
    return stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': f'File Concatenation for {repo_info.repo_name}',
                    'description': 'Repository file concatenation service'
                },
                'unit_amount': int(PRICE_USD * 100),  # Convert to cents
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=f'{base_url}success?session_id={{CHECKOUT_SESSION_ID}}',
        cancel_url=f'{base_url}cancel'
    )

@router.post("/verify-payment", response_model=PaymentVerificationResponse)
async def verify_payment(request: PaymentVerificationRequest):
    """Verify payment status."""
    try:
        session_id = request.checkout_session_id
        if session_id not in checkout_sessions:
            return PaymentVerificationResponse(
                status=PaymentStatus.FAILED,
                message="Invalid checkout session",
                can_proceed=False
            )
            
        # Get session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == "paid":
            checkout_sessions[session_id]["status"] = "completed"
            return PaymentVerificationResponse(
                status=PaymentStatus.COMPLETED,
                message="Payment successful",
                can_proceed=True
            )
        elif checkout_session.status == "expired":
            return PaymentVerificationResponse(
                status=PaymentStatus.FAILED,
                message="Payment session expired",
                can_proceed=False
            )
        else:
            return PaymentVerificationResponse(
                status=PaymentStatus.PENDING,
                message="Payment pending",
                can_proceed=False
            )
            
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/concatenate")
async def concatenate_files(request: ConcatenateRequest):
    """Concatenate files from a GitHub repository."""
    # Verify payment first
    session_id = request.checkout_session_id
    if session_id not in checkout_sessions or checkout_sessions[session_id]["status"] != "completed":
        raise HTTPException(status_code=402, detail="Payment required")
        
    try:
        # Clean up the repository URL - convert HttpUrl to string first
        repo_url = str(request.repo_url).strip()
        
        # Clone the repository using the cached handler
        try:
            clone_result = await github_handler.clone_repository(
                repo_url=repo_url,
                github_token=request.github_token
            )
            repo_path = clone_result.repo_path
            subdir = clone_result.subdir
            
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
        
        except InvalidRepositoryError as e:
            if "tree" in repo_url:
                e.details["suggestion"] = "The URL appears to be from the GitHub web interface. You can use either this URL or the repository's root URL."
            raise e
        except AuthenticationError as e:
            if "private" in str(e).lower():
                e.details["suggestion"] = "This appears to be a private repository. Please provide a GitHub token with appropriate access."
            raise e
        
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
        error_response = error_handler.create_error_response(e)
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response
        )
        
    except (FileSystemError, CacheError) as e:
        # Handle filesystem and cache errors
        logger.error(f"System error during concatenation: {e}")
        error_response = error_handler.create_error_response(e)
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response
        )
        
    except FileConcatenationError as e:
        # Handle concatenation-specific errors
        error_response = error_handler.create_error_response(e)
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response
        )
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error during concatenation: {e}")
        error_response = error_handler.create_error_response(e)
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

@router.get("/success")
async def payment_success(request: Request, session_id: str):
    """Handle successful payment redirect from Stripe."""
    try:
        # Verify the payment session
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status != "paid":
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_message": "Payment not completed"
                }
            )
        
        # Update session status
        if session_id in checkout_sessions:
            checkout_sessions[session_id]["status"] = "completed"
        
        # Return success page with repository form
        return templates.TemplateResponse(
            "success.html",
            {
                "request": request,
                "session_id": session_id,
                "repo_url": checkout_sessions.get(session_id, {}).get("repo_url", ""),
                "github_token": checkout_sessions.get(session_id, {}).get("github_token", "")
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling payment success: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": "Failed to process payment verification"
            }
        )

@router.get("/cancel")
async def payment_cancel(request: Request):
    """Handle cancelled payment from Stripe."""
    return templates.TemplateResponse(
        "cancel.html",
        {
            "request": request
        }
    ) 