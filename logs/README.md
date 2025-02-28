# Logging System

This directory contains the log files for the Combine Codes application. The logging system is designed to provide comprehensive information about the application's operation, errors, and performance.

## Log Files

The logging system creates and maintains the following log files:

- **info.log**: Contains informational messages about normal application operation (INFO level and above)
- **error.log**: Contains only error and critical messages (ERROR level and above)
- **debug.log**: Contains detailed debug information (DEBUG level and above)
- **client.log**: Contains logs from the client-side JavaScript application
- **payment.log**: Payment processing logs

## Log Rotation

All log files are configured with rotation to prevent excessive disk usage:

- Maximum file size: 5MB
- Maximum number of backup files: 5

When a log file reaches 5MB, it is renamed with a suffix (e.g., `info.log.1`) and a new file is created. Up to 5 backup files are kept for each log type.

## Log Format

Each log entry follows this format:

```
TIMESTAMP - MODULE_NAME - LOG_LEVEL - MESSAGE
```

Example:
```
2025-02-28 15:09:00,123 - app.api.routes - INFO - Processing repository: user/repo
```

## Console Output

In addition to file logging, the application also logs to the console with emoji formatting for better readability.

## Middleware Logging

HTTP requests are automatically logged by the `RequestLoggingMiddleware`, which captures:

- Request ID (UUID)
- HTTP method
- Path
- Client IP
- Status code
- Processing time
- User agent

## Client-Side Logging

The application includes a comprehensive client-side logging system that:

1. Logs events in the browser console with color formatting
2. Stores logs in localStorage with automatic rotation (max 1000 entries or 5MB)
3. Sends critical logs (WARN and ERROR levels) to the server via the `/api/logs` endpoint
4. Captures unhandled errors and promise rejections automatically
5. Provides session tracking for correlating user actions

### Client Log Levels

- **DEBUG**: Detailed information for debugging purposes
- **INFO**: General information about normal operation
- **WARN**: Warning about potential issues
- **ERROR**: Error that occurred during operation

### Using Client-Side Logging

```javascript
import { Logger } from './logger.js';

// Get a logger for your module
const logger = Logger.getLogger('your-module-name');

// Log at different levels
logger.debug('Detailed debug information');
logger.info('General information');
logger.warn('Warning about potential issues');
logger.error('Error occurred', { details: 'Additional information' });

// Log an error object with stack trace
try {
    // Some code that might throw
} catch (error) {
    logger.logError(error, 'Error context description');
}
```

### Viewing Client Logs

Client logs can be:
- Viewed in the browser console
- Exported as JSON using `Logger.exportLogs()`
- Downloaded as a file using `Logger.downloadLogs()`
- Cleared using `Logger.clearLogs()`

## Payment Logging

The payment logging system provides specialized logging for payment operations:

- Payment attempts
- Successful payments
- Failed payments
- Canceled payments
- Stripe API calls
- Stripe errors

### Payment Log Structure

Payment logs include:

- Timestamp
- Payment session ID
- Payment intent ID (when available)
- Payment amount
- Payment status
- Error details (for failed payments)
- Metadata about the repository being processed

## Error Handling

The application includes comprehensive error handling that ensures all exceptions are properly logged:

- Application-specific exceptions (GitHubException, StripeException, etc.)
- HTTP exceptions
- Validation exceptions
- Unhandled exceptions (with full traceback)

## Usage in Code

To use the logging system in your code:

```python
import logging

# Get a logger for your module
logger = logging.getLogger(__name__)

# Log messages at appropriate levels
logger.debug("Detailed debug information")
logger.info("General information about operation")
logger.warning("Warning about potential issues")
logger.error("Error that occurred during operation")
logger.critical("Critical error that requires immediate attention")
```

## Log Directory Structure

When the application is running with log rotation enabled, you may see files like:

```
logs/
├── README.md
├── client.log
├── client.log.1
├── debug.log
├── debug.log.1
├── debug.log.2
├── error.log
├── error.log.1
├── info.log
├── info.log.1
├── info.log.2
├── payment.log
├── payment.log.1
└── payment.log.2
```

## Maintenance

Log files should be periodically archived or deleted as part of system maintenance, especially in production environments where the application runs for extended periods.
