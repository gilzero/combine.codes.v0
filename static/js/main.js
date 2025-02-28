/**
 * @fileoverview Main application entry point and orchestration.
 * 
 * This file is responsible for:
 * - Application initialization and bootstrapping
 * - Global state management (ignorePatterns, currentRepoName, lastRequest)
 * - Event listener setup and coordination
 * - Button animations and UI interactions
 * - Global cleanup functionality
 * 
 * @requires ./ui.js
 * @requires ./repository.js
 * @requires ./visualization.js
 * @requires ./payment.js
 * @requires ./logger.js
 */
import { initializeTheme, toggleTheme } from './ui.js';
import { handleRepositorySubmit, validateInput, setupPaymentButtons } from './repository.js';
import { displayResults, exportAsImage, exportAsPDF, triggerConfetti } from './visualization.js';
import { verifyAndProcessPayment } from './payment.js';
import { Logger, logger } from './logger.js';

// Global state
export let ignorePatterns = [];
export let currentRepoName = '';
export let lastRequest = null;

// Re-export necessary functions for global use
export { initializeTheme, toggleTheme } from './ui.js';
export { handleRepositorySubmit };
export { triggerConfetti };

export function initializeEventListeners() {
    const form = document.getElementById('repository-form');
    if (!form) {
        console.error('Repository form not found');
        return;
    }
    
    // Setup form handlers
    form.addEventListener('submit', handleRepositorySubmit);
    
    const repoUrlInput = document.getElementById('repo-url');
    if (repoUrlInput) {
        repoUrlInput.addEventListener('input', validateInput);
        repoUrlInput.addEventListener('paste', validateInput);
    }

    // Export handlers
    document.getElementById('export-png')?.addEventListener('click', exportAsImage);
    document.getElementById('export-pdf')?.addEventListener('click', exportAsPDF);

    // Theme toggle
    document.querySelector('.theme-toggle')?.addEventListener('click', toggleTheme);

    // Check for payment success
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    if (sessionId) {
        verifyAndProcessPayment(sessionId);
    }
}

function setupButtonAnimations() {
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            const circle = document.createElement('div');
            const d = Math.max(this.clientWidth, this.clientHeight);
            
            circle.style.width = circle.style.height = d + 'px';
            circle.style.left = e.clientX - this.offsetLeft - d/2 + 'px';
            circle.style.top = e.clientY - this.offsetTop - d/2 + 'px';
            circle.classList.add('ripple');
            
            this.appendChild(circle);
            setTimeout(() => circle.remove(), 600);
        });
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize logger
    Logger.configure({
        minLevel: 0, // DEBUG level
        enableConsole: true,
        enableLocalStorage: true,
        enableServerLogging: true,
        serverLogEndpoint: '/api/logs',
        serverLogThreshold: 2 // WARN level and above
    });
    
    logger.info('Application initialized');
    
    // Initialize UI
    initializeTheme();
    initializeEventListeners();
    
    // Check for payment success
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    if (sessionId) {
        verifyAndProcessPayment(sessionId);
    }
});

// Cleanup function
export function cleanup() {
    document.getElementById('error-area').innerHTML = '';
    document.getElementById('confirmation-area').innerHTML = '';
    document.getElementById('result-area').innerHTML = '';
    document.getElementById('repo-url').value = '';
    document.getElementById('github-token').value = '';
    ignorePatterns = [];
    currentRepoName = '';
    lastRequest = null;
}

// Global exports for HTML event handlers
window.toggleTheme = toggleTheme;
window.triggerConfetti = triggerConfetti;
