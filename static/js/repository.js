/**
 * @fileoverview Repository form handling and validation.
 * 
 * Manages repository-related operations:
 * - Form submission handling
 * - GitHub URL validation
 * - Token validation
 * - Repository pre-check coordination
 * - Payment button setup
 * 
 * @requires ./ui.js
 * @requires ./api.js
 * @requires ./payment.js
 * @requires ./utils.js
 * @requires ./logger.js
 */

// Repository and form handling
import { showError, updateProgress, updateRepositoryDetails } from './ui.js';
import { preCheckRepository } from './api.js';
import { handlePayment, setActiveCheckoutSession } from './payment.js';
import { ErrorTypes, AppError } from './utils.js';
import { Logger } from './logger.js';
// import DOMPurify from 'dompurify';

// Get logger for this module
const logger = Logger.getLogger('repository');

// Form handling
export async function handleRepositorySubmit(event) {
    logger.info('Repository form submitted');
    console.log('Form submission handler called');
    event.preventDefault();
    
    const submitButton = event.target.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
    }
    
    try {
        // Get form data
        const formData = new FormData(event.target);
        const repoUrl = formData.get('repo_url');
        const token = formData.get('token') || '';
        
        logger.info('Processing repository submission', { 
            repoUrl: repoUrl,
            hasToken: !!token 
        });
        
        // Validate repository URL
        if (!repoUrl || !repoUrl.includes('github.com')) {
            logger.warn('Invalid GitHub URL submitted', { url: repoUrl });
            throw new AppError(
                ErrorTypes.INVALID_GITHUB_URL,
                'Please enter a valid GitHub repository URL'
            );
        }
        
        // Validate token format if provided
        if (token && !/^ghp_[a-zA-Z0-9]{36}$/.test(token)) {
            logger.warn('Invalid token format submitted');
            throw new AppError(
                ErrorTypes.INVALID_TOKEN_FORMAT,
                'Invalid token format. GitHub tokens should start with "ghp_" followed by 36 characters'
            );
        }
        
        // Update UI to show progress
        updateProgress(10, 'Checking repository...');
        
        // Pre-check repository
        const response = await preCheckRepository(repoUrl, token);
        
        if (response.success) {
            logger.info('Repository pre-check successful', { 
                repoName: response.repository_name,
                fileCount: response.file_count,
                totalSize: response.total_size
            });
            
            // Update UI with repository details
            updateRepositoryDetails(
                response.repository_name,
                response.file_count,
                response.total_size,
                response.checkout_session_id,
                response.checkout_url
            );
            
            // Store checkout session for later use
            setActiveCheckoutSession(response.checkout_session_id);
            
            // Update progress
            updateProgress(100, 'Repository checked successfully!');
        } else {
            logger.error('Repository pre-check failed', { 
                error: response.error,
                details: response.details 
            });
            
            throw new AppError(
                response.error,
                response.message || 'Failed to check repository',
                response.details || {}
            );
        }
    } catch (error) {
        logger.error('Error in repository submission', { 
            error: error.message,
            type: error.type || 'unknown'
        });
        
        // Handle errors
        if (error instanceof AppError) {
            showError(error.message);
        } else {
            showError('An unexpected error occurred. Please try again.');
        }
        
        // Reset progress
        updateProgress(0, '');
    } finally {
        // Re-enable submit button
        if (submitButton) {
            submitButton.disabled = false;
        }
    }
}

// Input validation
export function validateInput(event) {
    const input = event.target;
    const value = input.value;
    
    if (input.name === 'repo_url') {
        logger.debug('Repository URL input changed', { value: value });
        
        // Simple validation for GitHub URLs
        if (value && !value.includes('github.com')) {
            input.setCustomValidity('Please enter a valid GitHub repository URL');
        } else {
            input.setCustomValidity('');
        }
    }
    
    if (input.name === 'token') {
        logger.debug('Token input changed', { hasValue: !!value });
        
        // Validate token format if provided
        if (value && !/^ghp_[a-zA-Z0-9]{36}$/.test(value)) {
            input.setCustomValidity('Invalid token format. GitHub tokens should start with "ghp_" followed by 36 characters');
        } else {
            input.setCustomValidity('');
        }
    }
}

// Setup payment buttons
export function setupPaymentButtons() {
    logger.debug('Setting up payment buttons');
    
    const payWithCardButton = document.getElementById('pay-with-card');
    if (payWithCardButton) {
        payWithCardButton.addEventListener('click', function() {
            logger.info('Pay with card button clicked');
            handlePayment('card');
        });
    }
    
    const payWithCryptoButton = document.getElementById('pay-with-crypto');
    if (payWithCryptoButton) {
        payWithCryptoButton.addEventListener('click', function() {
            logger.info('Pay with crypto button clicked');
            handlePayment('crypto');
        });
    }
}