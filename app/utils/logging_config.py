import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emojis to log messages based on level."""
    
    EMOJI_LEVELS = {
        logging.DEBUG: "🔍",    # Magnifying glass for detailed inspection
        logging.INFO: "ℹ️ ",     # Information
        logging.WARNING: "⚠️ ",  # Warning sign
        logging.ERROR: "❌",    # Cross mark for errors
        logging.CRITICAL: "🚨"  # Emergency light for critical issues
    }
    
    EMOJI_KEYWORDS = {
        "Starting": "🚀",      # Rocket for start
        "Complete": "✅",      # Check mark for completion
        "Found": "🔎",        # Magnifying glass for finding
        "Processing": "⚙️ ",   # Gear for processing
        "Skipping": "⏭️ ",     # Skip forward for skipped items
        "Filtered": "🔍",     # Magnifying glass for filtering
        "Ignoring": "🚫",     # Prohibited for ignored items
        "Error": "❌",        # Cross mark for errors
        "Cleaning": "🧹",     # Broom for cleanup
        "Directory": "📁",    # Folder for directory operations
        "File": "📄",         # Page for file operations
        "Loading": "📥",      # Inbox for loading
        "Saving": "📥",       # Outbox for saving
        "Success": "🎉",      # Party popper for success
        "Failed": "💥",       # Collision for failure
        "Initialize": "🎬",   # Clapper board for initialization
    }

    def format(self, record):
        # Add level emoji
        level_emoji = self.EMOJI_LEVELS.get(record.levelno, "")
        
        # Add keyword emoji
        keyword_emoji = ""
        message = str(record.msg)
        for keyword, emoji in self.EMOJI_KEYWORDS.items():
            if keyword.lower() in message.lower():
                keyword_emoji = emoji
                break
        
        # Combine emojis with the original format
        record.msg = f"{level_emoji} {keyword_emoji} {record.msg}"
        return super().format(record)

class EmojiFilter(logging.Filter):
    def filter(self, record):
        record.emoji = EmojiFormatter.EMOJI_LEVELS.get(record.levelno, "")
        return True

class ClientLogFormatter(logging.Formatter):
    """Custom formatter for client-side logs with additional context."""
    
    def format(self, record):
        # Check if client_data is available in the record
        if hasattr(record, 'client_data'):
            # Extract client data
            client_data = record.client_data
            client_ip = client_data.get('client_ip', 'unknown')
            session_id = client_data.get('session_id', 'unknown')
            
            # Add client context to the message
            record.msg = f"[{client_ip}] [{session_id}] {record.msg}"
        
        return super().format(record)

def setup_logging():
    """
    Configure logging for the application.
    
    Returns:
        logging.Logger: The configured logger.
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Configure formatters
    console_formatter = logging.Formatter('%(emoji)s %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(emoji)s %(message)s')
    client_formatter = logging.Formatter('%(asctime)s - CLIENT - %(levelname)s - %(message)s - %(client_info)s')
    payment_formatter = logging.Formatter('%(asctime)s - PAYMENT - %(levelname)s - %(message)s')
    
    # Configure console handler with emoji formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(EmojiFilter())
    
    # Configure file handlers with rotation
    info_file_handler = RotatingFileHandler(
        logs_dir / "info.log", 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(file_formatter)
    info_file_handler.addFilter(EmojiFilter())
    
    error_file_handler = RotatingFileHandler(
        logs_dir / "error.log", 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(file_formatter)
    error_file_handler.addFilter(EmojiFilter())
    
    debug_file_handler = RotatingFileHandler(
        logs_dir / "debug.log", 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    debug_file_handler.setLevel(logging.DEBUG)
    debug_file_handler.setFormatter(file_formatter)
    debug_file_handler.addFilter(EmojiFilter())
    
    client_file_handler = RotatingFileHandler(
        logs_dir / "client.log", 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    client_file_handler.setLevel(logging.INFO)
    client_file_handler.setFormatter(client_formatter)
    
    payment_file_handler = RotatingFileHandler(
        logs_dir / "payment.log", 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    payment_file_handler.setLevel(logging.DEBUG)
    payment_file_handler.setFormatter(payment_formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(info_file_handler)
    root_logger.addHandler(error_file_handler)
    root_logger.addHandler(debug_file_handler)
    
    # Configure client logger
    client_logger = logging.getLogger("client")
    client_logger.setLevel(logging.INFO)
    client_logger.propagate = False  # Don't propagate to root logger
    client_logger.addHandler(client_file_handler)
    client_logger.addHandler(console_handler)  # Also log to console
    
    # Configure payment logger
    payment_logger = logging.getLogger("payment")
    payment_logger.setLevel(logging.DEBUG)
    payment_logger.propagate = False  # Don't propagate to root logger
    payment_logger.addHandler(payment_file_handler)
    payment_logger.addHandler(console_handler)  # Also log to console
    
    # Configure API request logger
    api_logger = logging.getLogger("api.request")
    api_logger.setLevel(logging.INFO)
    
    # Return the main application logger
    return logging.getLogger(__name__)