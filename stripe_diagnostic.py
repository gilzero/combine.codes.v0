"""
Stripe diagnostic script to check if the Stripe API key is being loaded correctly.
"""
import os
import stripe
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Stripe API key
stripe_key = os.getenv('STRIPE_SECRET_KEY')
stripe_key_masked = f"{stripe_key[:4]}...{stripe_key[-4:]}" if stripe_key and len(stripe_key) > 8 else None

print(f"Stripe API key configured in env: {'Yes' if stripe_key else 'No'}")
if stripe_key:
    print(f"Stripe key (masked): {stripe_key_masked}")
    print(f"Stripe key length: {len(stripe_key)}")

# Set Stripe API key
stripe.api_key = stripe_key

# Try to create a simple Stripe object
try:
    # Create a test customer
    customer = stripe.Customer.create(
        email="test@example.com",
        name="Test Customer"
    )
    print(f"Successfully created Stripe customer: {customer.id}")
    
    # Delete the test customer
    customer.delete()
    print("Successfully deleted test customer")
    
    print("Stripe API key is valid and working correctly")
except stripe.error.StripeError as e:
    print(f"Stripe API error: {str(e)}")
    print(f"Stripe API key is not valid or has insufficient permissions")
