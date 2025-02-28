"""
Stripe payment processing utilities for the Combine Codes service.
"""

import os
from typing import Optional, List
import stripe
from fastapi import HTTPException
from pydantic import BaseModel, Field, HttpUrl, constr
from enum import Enum
from app.utils.logging_config import setup_logging

logger = setup_logging()

class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    SUCCEEDED = 'succeeded'
    REQUIRES_PAYMENT_METHOD = 'requires_payment_method'
    REQUIRES_ACTION = 'requires_action'
    PROCESSING = 'processing'
    REQUIRES_CONFIRMATION = 'requires_confirmation'
    CANCELED = 'canceled'
    FAILED = 'failed'

class Currency(str, Enum):
    """Supported currency codes."""
    USD = 'usd'
    EUR = 'eur'
    GBP = 'gbp'
    JPY = 'jpy'
    CAD = 'cad'
    AUD = 'aud'
    CNY = 'cny'

class PaymentMetadata(BaseModel):
    """Payment metadata model."""
    service: str = Field(default="combine_codes_service", description="Service identifier")
    version: str = Field(default="1.0.0", description="Service version")
    environment: str = Field(default="development", description="Environment")
    repo_owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo_name: Optional[str] = Field(None, description="GitHub repository name")
    file_pattern: Optional[str] = Field(None, description="File pattern for processing")

class PaymentIntentCreate(BaseModel):
    """Payment intent creation request model."""
    amount: int = Field(default=50, ge=50, description="Amount in cents (minimum 50 cents)")
    currency: Currency = Field(default=Currency.USD, description="Currency code")
    payment_method_types: Optional[List[str]] = Field(None, description="Allowed payment methods")
    metadata: Optional[PaymentMetadata] = Field(None, description="Payment metadata")

class PaymentIntentResponse(BaseModel):
    """Payment intent creation response model."""
    client_secret: str = Field(..., description="Client secret for frontend processing")
    payment_intent_id: str = Field(..., description="Payment intent ID")
    amount: int = Field(..., description="Amount in cents")
    currency: str = Field(..., description="Currency code in uppercase")
    status: str = Field(default="requires_payment_method", description="Payment status")

class PaymentConfirmation(BaseModel):
    """Payment confirmation response model."""
    status: str = Field(..., description="Payment status")
    payment_status: PaymentStatus = Field(..., description="Detailed payment status")
    amount_received: int = Field(..., description="Amount received in cents")
    currency: str = Field(..., description="Currency code in uppercase")
    payment_method: Optional[str] = Field(None, description="Payment method used")

class RefundRequest(BaseModel):
    """Refund request model."""
    payment_intent_id: str = Field(..., description="Payment intent ID to refund")
    amount: Optional[int] = Field(None, description="Amount to refund in cents")
    reason: Optional[str] = Field(None, description="Reason for refund")

class RefundResponse(BaseModel):
    """Refund response model."""
    status: str = Field(..., description="Refund status")
    refund_id: str = Field(..., description="Refund ID")
    amount_refunded: int = Field(..., description="Amount refunded in cents")
    currency: str = Field(..., description="Currency code in uppercase")
    refund_status: str = Field(..., description="Detailed refund status")

class StripeService:
    """Service class for handling Stripe payment operations."""
    
    def __init__(self):
        self.stripe = stripe
        self.stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.stripe.api_version = "2023-10-16"  # Using latest stable API version
        
    def create_payment_intent(
        self, 
        data: Optional[PaymentIntentCreate] = None,
    ) -> PaymentIntentResponse:
        """Create a payment intent with improved validation and error handling."""
        try:
            # Use default values if no data provided
            if not data:
                data = PaymentIntentCreate()

            # Setup payment intent parameters
            intent_params = {
                "amount": data.amount,
                "currency": data.currency.value,
                "metadata": data.metadata.dict() if data.metadata else PaymentMetadata().dict(),
                "automatic_payment_methods": {"enabled": True},
            }
            
            if data.payment_method_types:
                intent_params["payment_method_types"] = data.payment_method_types
            
            # Create the payment intent
            intent = stripe.PaymentIntent.create(**intent_params)
            
            return PaymentIntentResponse(
                client_secret=intent.client_secret,
                payment_intent_id=intent.id,
                amount=intent.amount,
                currency=intent.currency.upper(),
                status=intent.status
            )
            
        except stripe.error.CardError as e:
            logger.error(f"Card error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "payment_failed",
                    "message": e.user_message,
                    "code": e.code,
                    "decline_code": getattr(e, 'decline_code', None)
                }
            )
            
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid parameters: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_request",
                    "message": str(e),
                    "param": e.param
                }
            )
            
        except stripe.error.AuthenticationError:
            logger.critical("Stripe authentication failed")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "configuration_error",
                    "message": "Payment service configuration error"
                }
            )
            
        except stripe.error.APIConnectionError:
            logger.error("Failed to connect to Stripe API")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "service_unavailable",
                    "message": "Payment service is temporarily unavailable"
                }
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in payment processing: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "server_error",
                    "message": "An unexpected error occurred"
                }
            )

    def confirm_payment_intent(self, payment_intent_id: str) -> PaymentConfirmation:
        """Confirm and validate a payment intent with enhanced validation."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == PaymentStatus.SUCCEEDED:
                return PaymentConfirmation(
                    status="success",
                    payment_status=intent.status,
                    amount_received=intent.amount_received,
                    currency=intent.currency.upper(),
                    payment_method=intent.payment_method_types[0] if intent.payment_method_types else None
                )
                
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "payment_incomplete",
                    "message": f"Payment is {intent.status}",
                    "payment_status": intent.status
                }
            )
                
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "payment_confirmation_failed",
                    "message": str(e)
                }
            )
            
    def create_refund(self, data: RefundRequest) -> RefundResponse:
        """Create a refund with improved validation."""
        try:
            refund_params = {
                "payment_intent": data.payment_intent_id,
            }
            
            if data.amount:
                refund_params["amount"] = data.amount
            if data.reason:
                refund_params["reason"] = data.reason
                
            refund = stripe.Refund.create(**refund_params)
            
            return RefundResponse(
                status="success",
                refund_id=refund.id,
                amount_refunded=refund.amount,
                currency=refund.currency.upper(),
                refund_status=refund.status
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "refund_failed",
                    "message": str(e)
                }
            ) 