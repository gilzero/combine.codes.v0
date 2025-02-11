/**
 * @fileoverview UI components and DOM manipulation utilities.
 * 
 * Handles all direct DOM interactions and UI updates, including:
 * - Toast notifications
 * - Error displays
 * - Progress updates
 * - Theme management
 * - Repository details display
 * 
 * @requires ./utils.js
 */

import { formatFileSize, formatNumber } from './utils.js';
import { ErrorTypes, AppError } from './utils.js';

export function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast animate__animated animate__fadeInRight ${type}`;
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi bi-${type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
            <strong class="me-auto">Notification</strong>
            <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.remove('animate__fadeInRight');
        toast.classList.add('animate__fadeOutRight');
        setTimeout(() => toast.remove(), 1000);
    }, 3000);
}

export function showError(error) {
    const errorArea = document.getElementById('error-area');
    if (!errorArea) {
        console.error('Error area not found');
        return;
    }

    let message, suggestion, action;

    if (error instanceof AppError) {
        ({ message, suggestion, action } = getErrorDetails(error));
    } else {
        message = error.message || 'An unexpected error occurred';
        suggestion = 'Please try again or contact support if the problem persists';
    }

    errorArea.innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            <strong>${message}</strong>
            ${suggestion ? `<br><small class="text-muted">${suggestion}</small>` : ''}
            ${action ? `<br><div class="mt-2">${action}</div>` : ''}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
}

function getErrorDetails(error) {
    switch (error.type) {
        case ErrorTypes.INVALID_GITHUB_URL:
            return {
                message: 'Invalid GitHub repository URL',
                suggestion: 'Please enter a valid GitHub repository URL (e.g., https://github.com/owner/repo)',
                action: '<button class="btn btn-sm btn-outline-danger" onclick="document.getElementById(\'repo-url\').focus()">Edit URL</button>'
            };

        case ErrorTypes.GITHUB_RATE_LIMIT:
            return {
                message: 'GitHub API rate limit exceeded',
                suggestion: error.details.resetTime 
                    ? `Rate limit will reset in ${formatTimeRemaining(error.details.resetTime)}`
                    : 'Please try again later or provide a GitHub token',
                action: '<button class="btn btn-sm btn-outline-primary" onclick="document.getElementById(\'github-token\').focus()">Add Token</button>'
            };

        case ErrorTypes.GITHUB_ACCESS_DENIED:
            return {
                message: 'Access to repository denied',
                suggestion: 'This might be a private repository or the token might not have sufficient permissions',
                action: '<button class="btn btn-sm btn-outline-primary" onclick="document.getElementById(\'github-token\').focus()">Update Token</button>'
            };

        case ErrorTypes.PAYMENT_FAILED:
            return {
                message: 'Payment failed',
                suggestion: error.details.reason || 'Please check your payment details and try again',
                action: '<button class="btn btn-sm btn-outline-primary" onclick="window.handlePayment()">Retry Payment</button>'
            };

        case ErrorTypes.API_TIMEOUT:
            return {
                message: 'Request timed out',
                suggestion: 'The server is taking too long to respond. Please try again.',
                action: '<button class="btn btn-sm btn-outline-primary" onclick="window.location.reload()">Refresh Page</button>'
            };

        default:
            return {
                message: error.message || 'An unexpected error occurred',
                suggestion: 'Please try again or contact support if the problem persists'
            };
    }
}

function formatTimeRemaining(resetTime) {
    const minutes = Math.ceil((new Date(resetTime) - new Date()) / (1000 * 60));
    return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
}

export function updateProgress(value) {
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = `${value}%`;
        progressBar.setAttribute('aria-valuenow', value);
    }
}

export function displayResults(data) {
    if (!data || !data.statistics) {
        showError('Invalid results data');
        return;
    }

    const result = document.getElementById('result');
    const stats = data.statistics;

    result.innerHTML = `
        <div class="card shadow-sm success-animate">
            <div class="card-header bg-success text-white d-flex align-items-center">
                <i class="bi bi-check-circle-fill me-2"></i>
                <span class="flex-grow-1">Processing Complete!</span>
                <button class="btn btn-sm btn-outline-light" onclick="triggerConfetti()">
                    <i class="bi bi-stars"></i> Celebrate
                </button>
            </div>
            <div class="card-body">
                <!-- Statistics Cards -->
                <div class="row g-3 mb-4">
                    <div class="col-md-3">
                        <div class="card h-100 border-primary">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Files Processed</h6>
                                <h2 class="card-title mb-0 text-primary">
                                    ${formatNumber(stats.file_stats.processed_files)}
                                    <small class="text-muted">/ ${formatNumber(stats.file_stats.total_files)}</small>
                                </h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100 border-info">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Total Size</h6>
                                <h2 class="card-title mb-0 text-info">
                                    ${formatFileSize(stats.file_stats.total_size)}
                                </h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100 border-success">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Lines of Code</h6>
                                <h2 class="card-title mb-0 text-success">
                                    ${formatNumber(stats.file_stats.total_lines - stats.file_stats.empty_lines - stats.file_stats.comment_lines)}
                                </h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100 border-warning">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Directories</h6>
                                <h2 class="card-title mb-0 text-warning">
                                    ${formatNumber(stats.dir_stats.total_dirs)}
                                </h2>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Download Button -->
                <div class="mt-4 text-center">
                    <a href="/download/${data.output_file}" class="btn btn-success btn-lg">
                        <i class="bi bi-download me-2"></i>
                        Download Combined Files
                    </a>
                    <div class="text-muted mt-2">
                        <small>
                            <i class="bi bi-info-circle me-1"></i>
                            Output file ready
                        </small>
                    </div>
                </div>
            </div>
        </div>`;

    // Show export buttons
    document.getElementById('exportButtons').classList.remove('d-none');
}

export function updateRepositoryDetails(preCheckData) {
    if (!preCheckData) {
        return;
    }

    const detailsHtml = `
        <div class="card">
            <div class="card-header">
                <h5 class="card-title mb-0">Repository Details</h5>
            </div>
            <div class="card-body">
                <dl class="row mb-0">
                    <dt class="col-sm-4">Repository:</dt>
                    <dd class="col-sm-8">${preCheckData.owner}/${preCheckData.repo_name}</dd>
                    
                    <dt class="col-sm-4">Estimated Files:</dt>
                    <dd class="col-sm-8">${preCheckData.estimated_file_count ? formatNumber(preCheckData.estimated_file_count) : 'Calculating...'}</dd>
                    
                    <dt class="col-sm-4">Repository Size:</dt>
                    <dd class="col-sm-8">${preCheckData.repository_size_kb ? formatFileSize(preCheckData.repository_size_kb * 1024) : 'Calculating...'}</dd>
                    
                    <dt class="col-sm-4">Price:</dt>
                    <dd class="col-sm-8">$${preCheckData.price_usd.toFixed(2)} USD</dd>
                </dl>
            </div>
            <div class="card-footer text-end">
                <button type="button" id="cancel-payment" class="btn btn-secondary me-2">Cancel</button>
                <button type="button" id="proceed-payment" class="btn btn-primary">
                    <i class="bi bi-credit-card me-2"></i>Proceed to Payment
                </button>
            </div>
        </div>
    `;
    
    document.getElementById('confirmation-area').innerHTML = detailsHtml;
}

// Theme handling
export function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    setTheme(currentTheme === 'dark' ? 'light' : 'dark');
}

export function setTheme(theme) {
    try {
        if (theme !== 'dark' && theme !== 'light') {
            throw new Error('Invalid theme value');
        }
        document.documentElement.setAttribute('data-bs-theme', theme);
        const icon = document.querySelector('[data-theme-icon]');
        const toggle = document.querySelector('.theme-toggle');
        icon.className = theme === 'dark' ? 'bi bi-moon-stars-fill' : 'bi bi-sun-fill';
        toggle.setAttribute('aria-pressed', theme === 'dark');
        localStorage.setItem('theme', theme);
    } catch (error) {
        console.error('Theme error:', error);
        // Fallback to light theme
        document.documentElement.setAttribute('data-bs-theme', 'light');
    }
}

export function initializeTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        setTheme(savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        setTheme('dark');
    }

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('theme')) {
            setTheme(e.matches ? 'dark' : 'light');
        }
    });
} 