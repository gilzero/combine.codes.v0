"""
Payment logging utility for tracking payment-related operations.

This module provides specialized logging for payment operations,
including Stripe API calls, payment status changes, and error handling.
"""

import logging
import json
from typing import Any, Dict, Optional
import stripe

# Configure logger
logger = logging.getLogger("payment")

def log_payment_attempt(session_id: str, amount: float, metadata: Dict[str, Any]) -> None:
    """
    Log a payment attempt.
    
    Args:
        session_id: The Stripe checkout session ID
        amount: The payment amount
        metadata: Additional metadata about the payment
    """
    logger.info(
        f"Payment attempt initiated: {session_id} for ${amount:.2f}",
        extra={
            "session_id": session_id,
            "amount": amount,
            "metadata": json.dumps(metadata)
        }
    )

def log_payment_success(session_id: str, payment_intent_id: Optional[str] = None) -> None:
    """
    Log a successful payment.
    
    Args:
        session_id: The Stripe checkout session ID
        payment_intent_id: The Stripe payment intent ID, if available
    """
    logger.info(
        f"Payment successful: {session_id} (Payment Intent: {payment_intent_id or 'N/A'})",
        extra={
            "session_id": session_id,
            "payment_intent_id": payment_intent_id,
            "status": "success"
        }
    )

def log_payment_failure(session_id: str, error: str, error_code: Optional[str] = None) -> None:
    """
    Log a failed payment.
    
    Args:
        session_id: The Stripe checkout session ID
        error: The error message
        error_code: The error code, if available
    """
    logger.error(
        f"Payment failed: {session_id} - {error} (Code: {error_code or 'N/A'})",
        extra={
            "session_id": session_id,
            "error": error,
            "error_code": error_code,
            "status": "failed"
        }
    )

def log_payment_canceled(session_id: str) -> None:
    """
    Log a canceled payment.
    
    Args:
        session_id: The Stripe checkout session ID
    """
    logger.info(
        f"Payment canceled: {session_id}",
        extra={
            "session_id": session_id,
            "status": "canceled"
        }
    )

def log_stripe_api_call(method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a Stripe API call.
    
    Args:
        method: The HTTP method (GET, POST, etc.)
        endpoint: The API endpoint
        params: The parameters sent to the API (sensitive data will be masked)
    """
    # Mask sensitive data
    masked_params = None
    if params:
        masked_params = params.copy()
        if "card" in masked_params:
            masked_params["card"] = "**masked**"
        if "api_key" in masked_params:
            masked_params["api_key"] = "**masked**"
    
    logger.debug(
        f"Stripe API call: {method} {endpoint}",
        extra={
            "method": method,
            "endpoint": endpoint,
            "params": json.dumps(masked_params) if masked_params else None
        }
    )

def log_stripe_error(error: stripe.error.StripeError) -> None:
    """
    Log a Stripe API error.
    
    Args:
        error: The Stripe error object
    """
    error_dict = {
        "type": error.__class__.__name__,
        "message": str(error),
        "code": getattr(error, "code", None),
        "param": getattr(error, "param", None),
        "http_status": getattr(error, "http_status", None),
    }
    
    logger.error(
        f"Stripe API error: {error_dict['type']} - {error_dict['message']}",
        extra={
            "error": json.dumps(error_dict),
            "http_status": error_dict["http_status"]
        }
    )
