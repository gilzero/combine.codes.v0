/**
 * @fileoverview API communication and request handling.
 * 
 * Manages all external API interactions:
 * - Repository pre-check requests
 * - Payment verification
 * - File concatenation requests
 * - Error handling and timeout management
 * - Response transformation
 * 
 * @requires ./utils.js
 * @requires ./ui.js
 */

import { showError } from './ui.js';
import { ErrorTypes, AppError } from './utils.js';

// Add request timeout
const TIMEOUT_MS = 30000;

export async function preCheckRepository(repoUrl, githubToken) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
        const response = await fetch('/pre-check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                repo_url: repoUrl,
                github_token: githubToken || null,
                base_url: window.location.origin + '/'
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const error = await response.json();
            throw handleApiError(error);
        }

        return response.json();
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new AppError(
                ErrorTypes.API_TIMEOUT,
                'Request timed out',
                { endpoint: 'pre-check' }
            );
        }
        throw error;
    }
}

function handleApiError(error) {
    switch (error.detail?.error_type) {
        case 'RateLimitExceeded':
            return new AppError(
                ErrorTypes.GITHUB_RATE_LIMIT,
                'GitHub API rate limit exceeded',
                { resetTime: error.detail.reset_at }
            );

        case 'RepositoryNotFound':
            return new AppError(
                ErrorTypes.GITHUB_NOT_FOUND,
                'Repository not found',
                { requiresToken: error.detail.requires_token }
            );

        case 'AuthenticationError':
            return new AppError(
                ErrorTypes.GITHUB_ACCESS_DENIED,
                'Authentication failed',
                { reason: error.detail.message }
            );

        default:
            return new AppError(
                error.detail?.error_type || 'unknown',
                error.detail?.message || 'An unexpected error occurred',
                error.detail
            );
    }
}

export async function verifyPayment(sessionId) {
    const response = await fetch('/verify-payment', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            checkout_session_id: sessionId
        }),
    });

    if (!response.ok) {
        throw new Error('Payment verification failed');
    }

    return response.json();
}

export async function processConcatenation(sessionId, repoUrl, githubToken) {
    const response = await fetch('/concatenate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            repo_url: repoUrl,
            github_token: githubToken || null,
            checkout_session_id: sessionId
        }),
    });

    if (!response.ok) {
        throw new Error('Concatenation failed');
    }

    return response.json();
} 