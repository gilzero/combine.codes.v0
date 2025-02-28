# Log Analysis Guide

This document provides guidance on how to analyze the application logs using the `log_analyzer.py` script.

## Basic Usage

```bash
# Analyze all logs
./log_analyzer.py

# Analyze only error logs
./log_analyzer.py --type error

# Analyze logs from the last 7 days
./log_analyzer.py --days 7

# Analyze payment logs
./log_analyzer.py --type payment

# Save analysis results to a JSON file
./log_analyzer.py --output log_analysis.json
```

## Analysis Types

The log analyzer supports the following analysis types:

- `info`: Analyze general information logs
- `error`: Analyze error logs
- `debug`: Analyze debug logs
- `client`: Analyze client-side logs
- `payment`: Analyze payment processing logs
- `all`: Analyze all log types (default)

## Output Format

The script provides a human-readable summary of log statistics:

- Total number of log entries
- Distribution of log entries by level (INFO, ERROR, etc.)
- Top modules by log volume
- Most common error messages
- Recent errors
- Payment statistics (for payment logs)

## Payment Log Analysis

Payment log analysis includes:

- Total payment events
- Number of payment attempts
- Number of successful payments
- Number of failed payments
- Number of canceled payments
- Stripe API calls
- Stripe errors
- Payment distribution by day
- Recent payment failures

## Advanced Usage

### Filtering by Date Range

```bash
# Analyze logs from the last 24 hours
./log_analyzer.py --days 1

# Analyze logs from the last week
./log_analyzer.py --days 7

# Analyze logs from the last month
./log_analyzer.py --days 30
```

### Combining Options

```bash
# Analyze payment logs from the last week
./log_analyzer.py --type payment --days 7

# Analyze error logs from the last day and save to JSON
./log_analyzer.py --type error --days 1 --output errors.json
```

### Using with Other Tools

The log analyzer can be combined with other tools for more advanced analysis:

```bash
# Generate a daily report
./log_analyzer.py --days 1 --output daily_report.json

# Monitor for critical errors
./log_analyzer.py --type error | grep CRITICAL

# Send analysis results via email
./log_analyzer.py | mail -s "Log Analysis Report" admin@example.com
```

## Troubleshooting

If you encounter issues with the log analyzer:

1. Ensure the log files exist in the `logs` directory
2. Check that the log files have the expected format
3. Verify that you have read permissions for the log files
4. For JSON output issues, check disk space and write permissions

## Example Output

```
Info Log Analysis (last 7 days)
==============================
Total entries: 1250

Entries by level:
  INFO: 1150
  WARNING: 75
  ERROR: 25

Top 5 modules by log volume:
  app.core.github_handler: 450
  app.api.routes: 350
  app.middleware.logging_middleware: 250
  app.utils.error_handler: 100
  app.core.file_concatenator: 100

Top 5 error messages:
  (10) Failed to clone repository: Repository not found
  (5) Stripe API key not configured
  (4) Invalid file type: .exe
  (3) File size exceeds limit: 15MB
  (3) Connection timeout when accessing GitHub API

Recent errors:
  2023-04-01 12:34:56,789 - app.api.routes - Failed to create Stripe checkout session: No API key provided...
```
