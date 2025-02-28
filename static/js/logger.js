/**
 * @fileoverview Client-side logging system.
 * 
 * Provides a centralized logging system for the frontend with:
 * - Multiple log levels (debug, info, warn, error)
 * - Console output with styling
 * - Optional server-side logging via API
 * - Log persistence in localStorage (configurable)
 * - Log rotation for localStorage
 * 
 * Usage:
 * import { Logger } from './logger.js';
 * const logger = Logger.getLogger('component-name');
 * logger.info('User clicked button');
 * logger.error('Failed to load data', { error: err });
 */

// Log levels with numeric values for comparison
const LogLevels = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3
};

// Color schemes for console output
const LogColors = {
    DEBUG: 'color: #6c757d',
    INFO: 'color: #0d6efd',
    WARN: 'color: #ffc107; font-weight: bold',
    ERROR: 'color: #dc3545; font-weight: bold'
};

// Maximum number of logs to keep in localStorage
const MAX_LOGS = 1000;

// Maximum size of logs in localStorage (5MB)
const MAX_LOG_SIZE = 5 * 1024 * 1024;

/**
 * Main Logger class
 */
export class Logger {
    /**
     * Create a new logger instance
     * @param {string} name - Logger name (usually component or module name)
     */
    constructor(name) {
        this.name = name;
        this.minLevel = LogLevels.INFO; // Default minimum level
        this.enableConsole = true;
        this.enableLocalStorage = true;
        this.enableServerLogging = false;
        this.serverLogEndpoint = '/api/logs';
        this.serverLogThreshold = LogLevels.ERROR; // Only send errors to server by default
    }

    /**
     * Get or create a logger instance by name
     * @param {string} name - Logger name
     * @returns {Logger} Logger instance
     */
    static getLogger(name) {
        if (!Logger.instances) {
            Logger.instances = new Map();
        }
        
        if (!Logger.instances.has(name)) {
            Logger.instances.set(name, new Logger(name));
        }
        
        return Logger.instances.get(name);
    }

    /**
     * Configure all logger instances
     * @param {Object} config - Configuration object
     */
    static configure(config = {}) {
        const {
            minLevel = LogLevels.INFO,
            enableConsole = true,
            enableLocalStorage = true,
            enableServerLogging = false,
            serverLogEndpoint = '/api/logs',
            serverLogThreshold = LogLevels.ERROR
        } = config;

        // Apply configuration to all existing loggers
        if (Logger.instances) {
            Logger.instances.forEach(logger => {
                logger.minLevel = minLevel;
                logger.enableConsole = enableConsole;
                logger.enableLocalStorage = enableLocalStorage;
                logger.enableServerLogging = enableServerLogging;
                logger.serverLogEndpoint = serverLogEndpoint;
                logger.serverLogThreshold = serverLogThreshold;
            });
        }
    }

    /**
     * Log a message at the specified level
     * @param {string} level - Log level (DEBUG, INFO, WARN, ERROR)
     * @param {string} message - Log message
     * @param {Object} data - Additional data to log
     */
    log(level, message, data = {}) {
        // Skip if level is below minimum
        if (LogLevels[level] < this.minLevel) {
            return;
        }

        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            name: this.name,
            message,
            data,
            userAgent: navigator.userAgent,
            url: window.location.href,
            sessionId: this._getSessionId()
        };

        // Console logging
        if (this.enableConsole) {
            this._logToConsole(level, logEntry);
        }

        // LocalStorage logging
        if (this.enableLocalStorage) {
            this._logToLocalStorage(logEntry);
        }

        // Server logging (only for errors or configured threshold)
        if (this.enableServerLogging && LogLevels[level] >= this.serverLogThreshold) {
            this._logToServer(logEntry);
        }

        return logEntry;
    }

    /**
     * Log a debug message
     * @param {string} message - Log message
     * @param {Object} data - Additional data to log
     */
    debug(message, data = {}) {
        return this.log('DEBUG', message, data);
    }

    /**
     * Log an info message
     * @param {string} message - Log message
     * @param {Object} data - Additional data to log
     */
    info(message, data = {}) {
        return this.log('INFO', message, data);
    }

    /**
     * Log a warning message
     * @param {string} message - Log message
     * @param {Object} data - Additional data to log
     */
    warn(message, data = {}) {
        return this.log('WARN', message, data);
    }

    /**
     * Log an error message
     * @param {string} message - Log message
     * @param {Object} data - Additional data to log
     */
    error(message, data = {}) {
        return this.log('ERROR', message, data);
    }

    /**
     * Log an error object with stack trace
     * @param {Error} error - Error object
     * @param {string} context - Context description
     */
    logError(error, context = '') {
        const message = context ? `${context}: ${error.message}` : error.message;
        return this.error(message, {
            name: error.name,
            stack: error.stack,
            ...(error.details || {})
        });
    }

    /**
     * Get all logs from localStorage
     * @returns {Array} Array of log entries
     */
    static getLogs() {
        try {
            const logs = localStorage.getItem('application_logs');
            return logs ? JSON.parse(logs) : [];
        } catch (e) {
            console.error('Failed to retrieve logs from localStorage', e);
            return [];
        }
    }

    /**
     * Clear all logs from localStorage
     */
    static clearLogs() {
        localStorage.removeItem('application_logs');
    }

    /**
     * Export logs as JSON
     * @returns {string} JSON string of logs
     */
    static exportLogs() {
        const logs = Logger.getLogs();
        return JSON.stringify(logs, null, 2);
    }

    /**
     * Download logs as a file
     */
    static downloadLogs() {
        const logs = Logger.exportLogs();
        const blob = new Blob([logs], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `application-logs-${new Date().toISOString()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * Log to console with styling
     * @private
     */
    _logToConsole(level, logEntry) {
        const { timestamp, name, message, data } = logEntry;
        const prefix = `%c[${timestamp}] [${level}] [${name}]:`;
        const style = LogColors[level] || '';
        
        if (Object.keys(data).length > 0) {
            console.groupCollapsed(prefix, style, message);
            console.log('Details:', data);
            console.groupEnd();
        } else {
            console.log(prefix, style, message);
        }
    }

    /**
     * Log to localStorage with rotation
     * @private
     */
    _logToLocalStorage(logEntry) {
        try {
            let logs = Logger.getLogs();
            logs.push(logEntry);
            
            // Implement log rotation
            if (logs.length > MAX_LOGS) {
                logs = logs.slice(-MAX_LOGS);
            }
            
            // Check size and trim if needed
            const logsJson = JSON.stringify(logs);
            if (logsJson.length > MAX_LOG_SIZE) {
                // Remove oldest logs until under size limit
                while (logs.length > 0) {
                    logs.shift();
                    const newJson = JSON.stringify(logs);
                    if (newJson.length <= MAX_LOG_SIZE) {
                        break;
                    }
                }
            }
            
            localStorage.setItem('application_logs', JSON.stringify(logs));
        } catch (e) {
            console.error('Failed to write logs to localStorage', e);
        }
    }

    /**
     * Log to server via API
     * @private
     */
    _logToServer(logEntry) {
        try {
            fetch(this.serverLogEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(logEntry),
                // Don't wait for response
                keepalive: true
            }).catch(err => {
                // Silent fail - don't log errors about logging
                console.debug('Failed to send log to server', err);
            });
        } catch (e) {
            // Silent fail
            console.debug('Exception sending log to server', e);
        }
    }

    /**
     * Get or create a session ID
     * @private
     */
    _getSessionId() {
        let sessionId = sessionStorage.getItem('log_session_id');
        if (!sessionId) {
            sessionId = 'session_' + Math.random().toString(36).substring(2, 15);
            sessionStorage.setItem('log_session_id', sessionId);
        }
        return sessionId;
    }
}

// Export constants
export { LogLevels };

// Create default logger
export const logger = Logger.getLogger('app');

// Global error handler
window.addEventListener('error', (event) => {
    const errorLogger = Logger.getLogger('global');
    errorLogger.error('Uncaught error', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error ? {
            name: event.error.name,
            message: event.error.message,
            stack: event.error.stack
        } : null
    });
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
    const errorLogger = Logger.getLogger('global');
    errorLogger.error('Unhandled promise rejection', {
        reason: event.reason ? {
            name: event.reason.name,
            message: event.reason.message,
            stack: event.reason.stack
        } : event.reason
    });
});
