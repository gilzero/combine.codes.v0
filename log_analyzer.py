#!/usr/bin/env python3
"""
Log analyzer script for the Combine Codes application.

This script provides utilities for analyzing log files, generating statistics,
and identifying patterns or issues in the application logs.
"""

import os
import re
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

def parse_log_line(line):
    """Parse a log line into its components."""
    # Basic pattern for log lines: timestamp - module - level - message
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - ([^-]+) - ([^-]+) - (.+)'
    match = re.match(pattern, line)
    if match:
        timestamp, module, level, message = match.groups()
        return {
            'timestamp': timestamp,
            'module': module.strip(),
            'level': level.strip(),
            'message': message.strip()
        }
    return None

def analyze_log_file(file_path, days=None):
    """Analyze a log file and return statistics."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None
    
    # Calculate the cutoff date if days is specified
    cutoff_date = None
    if days:
        cutoff_date = datetime.now() - timedelta(days=days)
    
    # Counters for statistics
    stats = {
        'total_entries': 0,
        'entries_by_level': Counter(),
        'entries_by_module': Counter(),
        'entries_by_hour': Counter(),
        'error_messages': Counter(),
        'recent_errors': []
    }
    
    # Process the log file
    with open(file_path, 'r') as f:
        for line in f:
            entry = parse_log_line(line)
            if entry:
                stats['total_entries'] += 1
                stats['entries_by_level'][entry['level']] += 1
                stats['entries_by_module'][entry['module']] += 1
                
                # Parse timestamp and count by hour
                try:
                    timestamp = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S,%f')
                    if cutoff_date and timestamp < cutoff_date:
                        continue
                    
                    hour = timestamp.strftime('%Y-%m-%d %H')
                    stats['entries_by_hour'][hour] += 1
                    
                    # Collect error messages
                    if entry['level'] == 'ERROR':
                        # Extract the main error message without details
                        error_msg = re.sub(r'\{.*\}', '{...}', entry['message'])
                        stats['error_messages'][error_msg] += 1
                        
                        # Add to recent errors
                        stats['recent_errors'].append({
                            'timestamp': entry['timestamp'],
                            'module': entry['module'],
                            'message': entry['message']
                        })
                except ValueError:
                    pass
    
    # Sort recent errors by timestamp (newest first)
    stats['recent_errors'] = sorted(
        stats['recent_errors'], 
        key=lambda x: x['timestamp'], 
        reverse=True
    )[:10]  # Keep only the 10 most recent
    
    return stats

def analyze_payment_logs(file_path, days=None):
    """Analyze payment logs and return statistics."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None
    
    # Calculate the cutoff date if days is specified
    cutoff_date = None
    if days:
        cutoff_date = datetime.now() - timedelta(days=days)
    
    # Counters for statistics
    stats = {
        'total_payments': 0,
        'successful_payments': 0,
        'failed_payments': 0,
        'canceled_payments': 0,
        'payment_attempts': 0,
        'stripe_api_calls': 0,
        'stripe_errors': 0,
        'payment_by_day': Counter(),
        'recent_failures': []
    }
    
    # Process the log file
    with open(file_path, 'r') as f:
        for line in f:
            if 'PAYMENT' not in line:
                continue
            
            stats['total_payments'] += 1
            
            # Extract timestamp
            timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
            if timestamp_match:
                try:
                    timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S,%f')
                    if cutoff_date and timestamp < cutoff_date:
                        continue
                    
                    day = timestamp.strftime('%Y-%m-%d')
                    stats['payment_by_day'][day] += 1
                except ValueError:
                    pass
            
            # Count different payment events
            if 'Payment successful' in line:
                stats['successful_payments'] += 1
            elif 'Payment failed' in line:
                stats['failed_payments'] += 1
                # Add to recent failures
                stats['recent_failures'].append(line.strip())
            elif 'Payment canceled' in line:
                stats['canceled_payments'] += 1
            elif 'Payment attempt initiated' in line:
                stats['payment_attempts'] += 1
            elif 'Stripe API call' in line:
                stats['stripe_api_calls'] += 1
            elif 'Stripe API error' in line:
                stats['stripe_errors'] += 1
                # Add to recent failures
                stats['recent_failures'].append(line.strip())
    
    # Keep only the 10 most recent failures
    stats['recent_failures'] = stats['recent_failures'][-10:]
    
    return stats

def print_stats(stats, title):
    """Print statistics in a readable format."""
    print(f"\n{title}")
    print("=" * len(title))
    
    if not stats:
        print("No statistics available.")
        return
    
    print(f"Total entries: {stats['total_entries']}")
    
    print("\nEntries by level:")
    for level, count in sorted(stats['entries_by_level'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {level}: {count}")
    
    print("\nTop 5 modules by log volume:")
    for module, count in stats['entries_by_module'].most_common(5):
        print(f"  {module}: {count}")
    
    print("\nTop 5 error messages:")
    for error, count in stats['error_messages'].most_common(5):
        # Truncate long error messages
        error_msg = error[:100] + "..." if len(error) > 100 else error
        print(f"  ({count}) {error_msg}")
    
    print("\nRecent errors:")
    for error in stats['recent_errors']:
        print(f"  {error['timestamp']} - {error['module']} - {error['message'][:100]}...")

def print_payment_stats(stats, title):
    """Print payment statistics in a readable format."""
    print(f"\n{title}")
    print("=" * len(title))
    
    if not stats:
        print("No statistics available.")
        return
    
    print(f"Total payment events: {stats['total_payments']}")
    print(f"Payment attempts: {stats['payment_attempts']}")
    print(f"Successful payments: {stats['successful_payments']}")
    print(f"Failed payments: {stats['failed_payments']}")
    print(f"Canceled payments: {stats['canceled_payments']}")
    print(f"Stripe API calls: {stats['stripe_api_calls']}")
    print(f"Stripe errors: {stats['stripe_errors']}")
    
    print("\nPayments by day:")
    for day, count in sorted(stats['payment_by_day'].items()):
        print(f"  {day}: {count}")
    
    print("\nRecent payment failures:")
    for failure in stats['recent_failures']:
        print(f"  {failure[:150]}...")

def main():
    parser = argparse.ArgumentParser(description='Analyze log files for the Combine Codes application.')
    parser.add_argument('--log-dir', default='logs', help='Directory containing log files')
    parser.add_argument('--days', type=int, help='Only analyze logs from the last N days')
    parser.add_argument('--type', choices=['all', 'info', 'error', 'debug', 'client', 'payment'],
                        default='all', help='Type of logs to analyze')
    parser.add_argument('--output', help='Output file for JSON results')
    
    args = parser.parse_args()
    
    log_dir = Path(args.log_dir)
    days_str = f" (last {args.days} days)" if args.days else ""
    
    results = {}
    
    if args.type in ['all', 'info']:
        info_stats = analyze_log_file(log_dir / 'info.log', args.days)
        print_stats(info_stats, f"Info Log Analysis{days_str}")
        results['info'] = info_stats
    
    if args.type in ['all', 'error']:
        error_stats = analyze_log_file(log_dir / 'error.log', args.days)
        print_stats(error_stats, f"Error Log Analysis{days_str}")
        results['error'] = error_stats
    
    if args.type in ['all', 'debug']:
        debug_stats = analyze_log_file(log_dir / 'debug.log', args.days)
        print_stats(debug_stats, f"Debug Log Analysis{days_str}")
        results['debug'] = debug_stats
    
    if args.type in ['all', 'client']:
        client_stats = analyze_log_file(log_dir / 'client.log', args.days)
        print_stats(client_stats, f"Client Log Analysis{days_str}")
        results['client'] = client_stats
    
    if args.type in ['all', 'payment']:
        payment_stats = analyze_payment_logs(log_dir / 'payment.log', args.days)
        print_payment_stats(payment_stats, f"Payment Log Analysis{days_str}")
        results['payment'] = payment_stats
    
    if args.output:
        # Convert Counter objects to dictionaries for JSON serialization
        for log_type, stats in results.items():
            if stats:
                for key, value in stats.items():
                    if isinstance(value, Counter):
                        stats[key] = dict(value)
        
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
