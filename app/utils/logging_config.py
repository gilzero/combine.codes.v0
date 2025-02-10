import logging
import sys
import os

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

def setup_logging():
    """Configure logging with emoji formatter."""
    formatter = EmojiFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler with emojis
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handler with emojis
    log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'output', 'app.log')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Configure root logger
    logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
    return logging.getLogger(__name__) 