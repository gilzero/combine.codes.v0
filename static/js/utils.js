/**
 * @fileoverview Utility functions and error handling.
 * 
 * Pure utility functions with no side effects, including:
 * - Error types and custom error classes
 * - String formatting functions
 * - ID generation
 * - File name generation
 * - Number formatting
 * 
 * This file should not contain any DOM manipulation or API calls.
 * All functions should be pure and stateless.
 */

import { Logger } from './logger.js';

// Utility functions for formatting, IDs, etc.
/**
 * Generates a random 8-character hexadecimal ID
 * @returns {string} The generated ID
 */
export function generateUniqueId() {
    return 'xxxxxxxx'.replace(/[x]/g, () => {
        // Use more cryptographically secure random numbers for IDs
        const bytes = new Uint8Array(1);
        window.crypto.getRandomValues(bytes);
        return bytes[0].toString(16);
    });
}

export function generateUniqueFilename(repoName, extension) {
    const timestamp = new Date().toISOString()
        .replace(/[-:]/g, '')
        .replace('T', '_')
        .replace(/\..+/, '');
    const uniqueId = generateUniqueId();
    const pid = Math.floor(Math.random() * 100000);
    return `file-stats_${repoName}_${timestamp}_pid${pid}_${uniqueId}.${extension}`;
}

export function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Formats a number with commas as thousands separators
 * @param {number} num - The number to format
 * @returns {string} The formatted number
 */
export function formatNumber(num) {
    if (typeof num !== 'number') {
        return '0';
    }
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Add error types
export const ErrorTypes = {
    // User Input
    INVALID_GITHUB_URL: 'invalid_github_url',
    INVALID_TOKEN_FORMAT: 'invalid_token_format',
    
    // API
    GITHUB_RATE_LIMIT: 'github_rate_limit',
    GITHUB_NOT_FOUND: 'github_not_found',
    GITHUB_ACCESS_DENIED: 'github_access_denied',
    API_TIMEOUT: 'api_timeout',
    
    // Payment
    PAYMENT_FAILED: 'payment_failed',
    PAYMENT_EXPIRED: 'payment_expired',
    
    // UI/State
    INVALID_STATE: 'invalid_state',
    MISSING_ELEMENT: 'missing_element',
    INVALID_DATA: 'invalid_data'
};

export class AppError extends Error {
    constructor(type, message, details = {}) {
        super(message);
        this.type = type;
        this.details = details;
        this.timestamp = new Date();
        
        // Log the error
        const errorLogger = Logger.getLogger('error');
        errorLogger.error(message, {
            type: this.type,
            details: this.details,
            stack: this.stack
        });
    }
}