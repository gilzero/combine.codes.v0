"""
app/api/routes.py
API routes for the Combine Codes application.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
import stripe
import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from pydantic import BaseModel

from app.core.github_handler import GitHubHandler
from app.core.file_concatenator import FileConcatenator
from app.models.schemas import (
    RepositoryPreCheckRequest,
    RepositoryPreCheckResponse,
    ConcatenateRequest,
    ConcatenateResponse,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    PaymentStatus,
    GitHubError,
    AuthenticationError,
    RepositoryNotFoundError,
    InvalidRepositoryError,
    FileSystemError,
    CacheError,
)
from app.config.pattern_manager import PatternManager
from app.utils.payment_logger import (
    log_payment_attempt,
    log_payment_success,
    log_payment_failure,
    log_payment_canceled,
    log_stripe_api_call,
    log_stripe_error
)

# Configure logging
logger = logging.getLogger(__name__)
client_logger = logging.getLogger("client")

# Initialize router
router = APIRouter()

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize Stripe with explicit reload from environment
stripe_key = os.getenv("STRIPE_SECRET_KEY")
if stripe_key:
    stripe.api_key = stripe_key
    logger.info(f"Stripe initialized with API key (masked): {stripe_key[:4]}...{stripe_key[-4:]}")
else:
    logger.error("Stripe API key not found in environment variables")

# Initialize GitHub handler
github_handler = GitHubHandler(
    cache_dir=os.getenv("CACHE_DIR", "cache"),
    github_token=os.getenv("GITHUB_TOKEN"),
    cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
)

# Client log entry model
class ClientLogEntry(BaseModel):
    """Model for client-side log entries."""
    timestamp: str
    level: str
    name: str
    message: str
    data: Dict[str, Any] = {}
    userAgent: Optional[str] = None
    url: Optional[str] = None
    sessionId: Optional[str] = None

@router.post("/api/logs")
async def log_client_event(log_entry: ClientLogEntry, request: Request):
    """
    Endpoint for receiving client-side logs.
    
    Maps client log levels to server log levels and adds
    client IP and other request information.
    """
    # Map client log level to server log level
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR
    }
    
    level = level_map.get(log_entry.level, logging.INFO)
    
    # Add client IP and request info to log data
    log_data = {
        **log_entry.data,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": log_entry.userAgent,
        "url": log_entry.url,
        "session_id": log_entry.sessionId,
        "referer": request.headers.get("referer", "unknown"),
    }
    
    # Format the log message
    log_message = f"[CLIENT] [{log_entry.name}] {log_entry.message}"
    
    # Log with the appropriate level
    client_logger.log(level, log_message, extra={"client_data": log_data})
    
    return {"status": "logged"}

@router.get("/")
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
async def pre_check_repository(request: RepositoryPreCheckRequest) -> RepositoryPreCheckResponse:
    """
    Pre-check a GitHub repository before processing.
    Creates a Stripe checkout session for payment.
    """
    try:
        # Validate repository URL and check accessibility
        repo_info = await github_handler.pre_check_repository(str(request.repo_url), request.github_token)

        # Verify Stripe API key is set
        if not stripe.api_key:
            stripe_key = os.getenv("STRIPE_SECRET_KEY")
            if stripe_key:
                logger.warning("Stripe API key was not set. Resetting from environment.")
                stripe.api_key = stripe_key
            else:
                logger.error("Stripe API key not found in environment variables")
                raise ValueError("Stripe API key not configured")

        # Create Stripe checkout session
        logger.info(f"Creating Stripe checkout session for repository: {request.repo_url}")
        success_url = str(request.base_url).rstrip('/') + "/success?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = str(request.base_url).rstrip('/') + "/cancel"
        
        try:
            log_stripe_api_call("POST", "checkout.Session.create", {
                "payment_method_types": ["card"],
                "line_items": [{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Combine Codes Service"
                        },
                        "unit_amount": 50
                    },
                    "quantity": 1
                }],
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url
            })
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Combine Codes Service",
                            "description": "Combine all files in a GitHub repository into a single file",
                        },
                        "unit_amount": 50,  # $0.50 in cents
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'repo_url': str(request.repo_url),
                    'github_token': request.github_token or '',
                    'repository_size_kb': str(repo_info.size_kb or ''),
                    'estimated_file_count': str(repo_info.file_count or '')
                }
            )
            
            log_payment_attempt(
                session_id=checkout_session.id,
                amount=0.50,
                metadata={
                    'repo_url': str(request.repo_url),
                    'repository_size_kb': str(repo_info.size_kb or ''),
                    'estimated_file_count': str(repo_info.file_count or '')
                }
            )
            
            logger.info(f"Stripe checkout session created: {checkout_session.id}")
        except stripe.error.StripeError as e:
            log_stripe_error(e)
            logger.error(f"Failed to create Stripe checkout session: {str(e)}")
            logger.error(f"Stripe API Key configured: {'Yes' if stripe.api_key else 'No'}")
            logger.error(f"Stripe API Key length: {len(stripe.api_key) if stripe.api_key else 0}")
            raise

        return RepositoryPreCheckResponse(
            repo_name=repo_info.repo_name,
            owner=repo_info.owner,
            price_usd=0.50,
            checkout_session_id=checkout_session.id,
            status="ready",
            message="Repository is accessible and ready for processing",
            repository_size_kb=repo_info.size_kb,
            estimated_file_count=repo_info.file_count
        )

    except (GitHubError, stripe.error.StripeError) as e:
        if isinstance(e, stripe.error.StripeError):
            logger.error(f"Pre-check failed (Stripe Error): {str(e)}")
            logger.error(f"Stripe API Key configured: {'Yes' if stripe.api_key else 'No'}")
            logger.error(f"Stripe API Key length: {len(stripe.api_key) if stripe.api_key else 0}")
            raise HTTPException(status_code=400, detail={"message": str(e), "error_code": "STRIPE_ERROR"})
        else:
            logger.error(f"Pre-check failed (GitHub Error): {str(e)}")
            if isinstance(e, GitHubError):
                raise HTTPException(status_code=e.status_code, detail={"message": e.to_dict(), "error_code": "GITHUB_ERROR"})
            raise HTTPException(status_code=400, detail={"message": str(e), "error_code": "UNKNOWN_ERROR"})

@router.get("/success")
async def payment_success(request: Request, session_id: str):
    """Handle successful payment and show success page."""
    try:
        log_stripe_api_call("GET", "checkout.Session.retrieve", {"session_id": session_id})
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Log the successful payment
        payment_intent_id = session.payment_intent if hasattr(session, 'payment_intent') else None
        log_payment_success(session_id, payment_intent_id)
        
        logger.info(f"Payment successful for session: {session_id}")
        
        # Get repository details from session metadata
        repo_url = session.metadata.get('repo_url', 'Unknown repository')
        
        return templates.TemplateResponse(
            "success.html",
            {
                "request": request,
                "session_id": session_id,
                "repo_url": repo_url
            }
        )
    except stripe.error.StripeError as e:
        log_stripe_error(e)
        logger.error(f"Error retrieving checkout session: {str(e)}")
        raise HTTPException(status_code=400, detail={"message": str(e), "error_code": "STRIPE_ERROR"})

@router.get("/cancel")
async def payment_canceled(request: Request):
    """Handle canceled payment."""
    # Get session ID from query params if available
    session_id = request.query_params.get('session_id', 'Unknown')
    
    # Log the canceled payment
    log_payment_canceled(session_id)
    
    logger.info(f"Payment canceled for session: {session_id}")
    return templates.TemplateResponse("cancel.html", {"request": request})

@router.post("/concatenate", response_model=ConcatenateResponse)
async def concatenate_repository(request: ConcatenateRequest) -> ConcatenateResponse:
    """
    Combine all files in a GitHub repository into a single file.
    Requires a valid checkout session ID from a completed payment.
    """
    try:
        # Verify payment status
        session = stripe.checkout.Session.retrieve(request.checkout_session_id)
        if session.payment_status != "paid":
            raise HTTPException(
                status_code=402,
                detail="Payment required to process repository"
            )

        # Clone repository and combine files
        with github_handler as gh:
            clone_result = await gh.clone_repository(
                str(request.repo_url),
                request.github_token
            )
            
            # Use PatternManager to combine ignore patterns
            pattern_manager = PatternManager(user_ignores=request.additional_ignores)
            combined_ignores = pattern_manager.all_ignores
            
            # Log combined ignore patterns
            logger.info(f"Combined ignore patterns: {combined_ignores}")
            
            concatenator = FileConcatenator(
                repo_path=clone_result.repo_path,
                additional_ignores=combined_ignores
            )
            
            output_file = concatenator.concatenate()
            
            return ConcatenateResponse(
                status="success",
                message="Files combined successfully",
                output_file=str(output_file),
                statistics=concatenator.get_statistics()
            )

    except (GitHubError, FileSystemError, CacheError) as e:
        logger.error(f"Combining failed: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except stripe.error.StripeError as e:
        logger.error(f"Payment verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{filename:path}")
async def download_file(filename: str):
    """Download the concatenated file."""
    try:
        file_path = Path("output") / filename
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="text/plain"
        )
        
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-payment", response_model=PaymentVerificationResponse)
async def verify_payment(request: PaymentVerificationRequest) -> PaymentVerificationResponse:
    """Verify the payment status of a checkout session."""
    try:
        log_stripe_api_call("GET", "checkout.Session.retrieve", {"session_id": request.checkout_session_id})
        session = stripe.checkout.Session.retrieve(request.checkout_session_id)
        
        if session.payment_status == "paid":
            payment_intent_id = session.payment_intent if hasattr(session, 'payment_intent') else None
            log_payment_success(request.checkout_session_id, payment_intent_id)
            
            return PaymentVerificationResponse(
                status=PaymentStatus.COMPLETED,
                message="Payment completed successfully",
                checkout_session_id=request.checkout_session_id
            )
        elif session.status == "open":
            return PaymentVerificationResponse(
                status=PaymentStatus.PENDING,
                message="Payment is pending",
                checkout_session_id=request.checkout_session_id
            )
        else:
            log_payment_failure(
                request.checkout_session_id, 
                f"Payment not completed. Status: {session.payment_status}", 
                session.status
            )
            
            return PaymentVerificationResponse(
                status=PaymentStatus.FAILED,
                message=f"Payment failed or expired. Status: {session.payment_status}",
                checkout_session_id=request.checkout_session_id
            )
    except stripe.error.StripeError as e:
        log_stripe_error(e)
        logger.error(f"Payment verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail={"message": str(e), "error_code": "STRIPE_ERROR"})