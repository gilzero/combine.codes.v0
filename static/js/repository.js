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
 */

// Repository and form handling
import { showError, updateProgress, updateRepositoryDetails } from './ui.js';
import { preCheckRepository } from './api.js';
import { handlePayment, setActiveCheckoutSession } from './payment.js';
import { ErrorTypes, AppError } from './utils.js';

// Form handling
export async function handleRepositorySubmit(event) {
    console.log('Form submission handler called');
    event.preventDefault();
    
    const submitButton = event.target.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
    }
    
    try {
        const form = event.target;
        const repoUrl = form.querySelector('#repo-url')?.value.trim();
        const githubToken = form.querySelector('#github-token')?.value.trim();

        if (!repoUrl) {
            throw new AppError(
                ErrorTypes.INVALID_GITHUB_URL,
                'Repository URL is required'
            );
        }

        // Validate URL format
        const repoUrlPattern = /^https:\/\/github\.com\/[\w-]+\/[\w-]+$/;
        if (!repoUrlPattern.test(repoUrl)) {
            throw new AppError(
                ErrorTypes.INVALID_GITHUB_URL,
                'Invalid GitHub repository URL',
                { url: repoUrl }
            );
        }

        // Validate token format if provided
        if (githubToken && !/^ghp_[a-zA-Z0-9]{36}$/.test(githubToken)) {
            throw new AppError(
                ErrorTypes.INVALID_TOKEN_FORMAT,
                'Invalid GitHub token format',
                { suggestion: 'Token should start with "ghp_" followed by 36 characters' }
            );
        }

        // Show loading state
        updateProgress(10);

        // Pre-check repository
        const preCheckData = await preCheckRepository(repoUrl, githubToken);
        
        if (!preCheckData?.checkout_session_id) {
            throw new AppError(
                ErrorTypes.INVALID_DATA,
                'Invalid pre-check response',
                { response: preCheckData }
            );
        }

        // Update UI with repository details
        updateRepositoryDetails(preCheckData);
        setActiveCheckoutSession(preCheckData.checkout_session_id);

        // Setup payment buttons
        setupPaymentButtons();
        updateProgress(100);

    } catch (error) {
        console.error('Repository submission error:', error);
        showError(error);
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
        }
    }
}

export function validateInput(event) {
    const input = event.target;
    const repoUrlPattern = /^https:\/\/github\.com\/[\w-]+\/[\w-]+$/;
    
    if (!repoUrlPattern.test(input.value)) {
        input.setCustomValidity('Please enter a valid GitHub repository URL');
    } else {
        input.setCustomValidity('');
    }
}

export function setupPaymentButtons() {
    const cancelBtn = document.getElementById('cancel-payment');
    const proceedBtn = document.getElementById('proceed-payment');

    if (!cancelBtn || !proceedBtn) {
        throw new AppError(
            ErrorTypes.MISSING_ELEMENT,
            'Payment buttons not found',
            { elements: ['cancel-payment', 'proceed-payment'] }
        );
    }

    cancelBtn.addEventListener('click', () => {
        document.getElementById('confirmation-area').innerHTML = '';
        document.getElementById('error-area').innerHTML = '';
    });

    proceedBtn.addEventListener('click', handlePayment);
} 