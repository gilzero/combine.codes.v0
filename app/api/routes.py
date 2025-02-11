"""
API routes for the File Concatenator application.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
import stripe
import os
from pathlib import Path
from typing import Optional
import logging

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

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Initialize GitHub handler
github_handler = GitHubHandler(
    cache_dir=os.getenv("CACHE_DIR", "cache"),
    github_token=os.getenv("GITHUB_TOKEN"),
    cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
)

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
        await github_handler.pre_check_repository(str(request.repo_url), request.github_token)

        # Create Stripe checkout session
        success_url = str(request.base_url).rstrip('/') + "/success?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = str(request.base_url).rstrip('/') + "/cancel"
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Repository File Concatenation",
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
                'github_token': request.github_token or ''
            }
        )

        # Extract repository info from URL
        repo_info = github_handler.validate_github_url(str(request.repo_url))
        
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
        logger.error(f"Pre-check failed: {str(e)}")
        if isinstance(e, GitHubError):
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/success")
async def payment_success(request: Request, session_id: str):
    """Handle successful payment and show success page."""
    try:
        # Verify payment status
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != "paid":
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": "Payment not completed"}
            )

        # Get metadata from the session
        repo_url = session.metadata.get('repo_url') if session.metadata else None
        github_token = session.metadata.get('github_token') if session.metadata else None

        return templates.TemplateResponse(
            "success.html",
            {
                "request": request,
                "session_id": session_id,
                "repo_url": repo_url,
                "github_token": github_token
            }
        )

    except stripe.error.StripeError as e:
        logger.error(f"Payment verification failed: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)}
        )

@router.get("/cancel")
async def payment_canceled(request: Request):
    """Handle canceled payment."""
    return templates.TemplateResponse(
        "cancel.html",
        {"request": request}
    )

@router.post("/concatenate", response_model=ConcatenateResponse)
async def concatenate_repository(request: ConcatenateRequest) -> ConcatenateResponse:
    """
    Concatenate all files in a GitHub repository into a single file.
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

        # Clone repository and concatenate files
        with github_handler as gh:
            clone_result = await gh.clone_repository(
                str(request.repo_url),
                request.github_token
            )
            
            concatenator = FileConcatenator(
                repo_path=clone_result.repo_path,
                additional_ignores=request.additional_ignores
            )
            
            output_file = concatenator.concatenate()
            
            return ConcatenateResponse(
                status="success",
                message="Files concatenated successfully",
                output_file=str(output_file),
                statistics=concatenator.get_statistics()
            )

    except (GitHubError, FileSystemError, CacheError) as e:
        logger.error(f"Concatenation failed: {str(e)}")
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
        session = stripe.checkout.Session.retrieve(request.checkout_session_id)
        
        if session.payment_status == "paid":
            return PaymentVerificationResponse(
                status=PaymentStatus.COMPLETED,
                message="Payment completed successfully",
                can_proceed=True
            )
        elif session.payment_status == "unpaid":
            return PaymentVerificationResponse(
                status=PaymentStatus.FAILED,
                message="Payment failed or was declined",
                can_proceed=False
            )
        else:
            return PaymentVerificationResponse(
                status=PaymentStatus.PENDING,
                message="Payment is still processing",
                can_proceed=False
            )
            
    except stripe.error.StripeError as e:
        logger.error(f"Payment verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) 