/**
 * @fileoverview Payment processing and Stripe integration.
 * 
 * Handles all payment-related functionality:
 * - Stripe checkout integration
 * - Payment session management
 * - Payment verification with retry logic
 * - Payment error handling
 * 
 * @requires ./ui.js
 * @requires ./api.js
 * @requires ./utils.js
 */

import { showError } from './ui.js';
import { processConcatenation, verifyPayment } from './api.js';
import { displayResults } from './ui.js';
import { ErrorTypes, AppError } from './utils.js';

// Initialize Stripe
const stripe = Stripe(STRIPE_PUBLISHABLE_KEY);
let activeCheckoutSessionId = null;

export function setActiveCheckoutSession(sessionId) {
    if (!sessionId || typeof sessionId !== 'string') {
        throw new AppError(
            ErrorTypes.INVALID_STATE,
            'Invalid session ID',
            { sessionId }
        );
    }
    activeCheckoutSessionId = sessionId;
}

export async function handlePayment() {
    try {
        if (!activeCheckoutSessionId) {
            throw new AppError(
                ErrorTypes.INVALID_STATE,
                'No active checkout session',
                { suggestion: 'Please start the process again' }
            );
        }

        const result = await stripe.redirectToCheckout({
            sessionId: activeCheckoutSessionId
        });
        
        if (result.error) {
            throw new AppError(
                ErrorTypes.PAYMENT_FAILED,
                result.error.message,
                { 
                    reason: result.error.type,
                    code: result.error.code
                }
            );
        }
    } catch (error) {
        console.error('Payment error:', error);
        showError(error instanceof AppError ? error : new AppError(
            ErrorTypes.PAYMENT_FAILED,
            'Payment failed',
            { originalError: error.message }
        ));
    }
}

const MAX_RETRIES = 10;
let retryCount = 0;

export async function verifyAndProcessPayment(sessionId) {
    try {
        if (retryCount >= MAX_RETRIES) {
            throw new AppError(
                ErrorTypes.PAYMENT_EXPIRED,
                'Payment verification timeout',
                { 
                    maxRetries: MAX_RETRIES,
                    suggestion: 'Please try the payment process again'
                }
            );
        }

        const data = await verifyPayment(sessionId);
        
        if (data.can_proceed) {
            retryCount = 0;
            const repoUrl = document.getElementById('repo-url')?.value;
            const githubToken = document.getElementById('github-token')?.value;
            
            if (!repoUrl) {
                throw new AppError(
                    ErrorTypes.INVALID_STATE,
                    'Repository URL not found',
                    { suggestion: 'Please refresh and try again' }
                );
            }
            
            const result = await processConcatenation(sessionId, repoUrl, githubToken);
            displayResults(result);
        } else if (data.status === 'pending') {
            retryCount++;
            setTimeout(() => verifyAndProcessPayment(sessionId), 2000);
        } else {
            retryCount = 0;
            throw new AppError(
                ErrorTypes.PAYMENT_FAILED,
                data.message || 'Payment verification failed',
                { status: data.status }
            );
        }
    } catch (error) {
        retryCount = 0;
        console.error('Verification error:', error);
        showError(error instanceof AppError ? error : new AppError(
            ErrorTypes.PAYMENT_FAILED,
            'Payment verification failed',
            { originalError: error.message }
        ));
    }
}

export function cleanup() {
    activeCheckoutSessionId = null;
    retryCount = 0;
} 