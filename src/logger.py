# Import Python's built-in logging Library
import logging
# Import OS utilities for filesystem operations(Like making foleders)
import os
# Import datetime to timestamp log files with today's date
from datetime import datetime

# Name of the folder where logs will be stored
LOGS_DIR = "logs"
# Create the logs folder if it doesn't exist
os.makedirs(LOGS_DIR, exist_ok=True)

# Build a log file path like: logs/log_2025-08-05.log(changes daily)
LOG_FILE = os.path.join(
    LOGS_DIR, 
    f"log_{datetime.now().strftime('%Y-%m-%d')}.log"
)

# Configure the ROOT logger once for the whole program
logging.basicConfig(
    # Write all logs to this log file
    filename=LOG_FILE,
    # Log message format:
    # -%(asctime)s: Timestamp
    # -%(levelname)s: Log level (INFO, ERROR, etc)
    # -%(message)s: The log message text
    format="%(asctime)s - %(levelname)s - %(message)s",
    # minimum level to record (INFO and above)
    level=logging.INFO,
)

def get_logger(name):
    """Returns a named logger that inherits the root configuration above. 
    Use different names per module(e.g.,_name_) to identify sources."""
    # Get (or create) a logger with the given name
    logger = logging.getLogger(name)
    # Ensure this logger emits INFO and above (can be customized per logger)
    logger.setLevel(logging.INFO)
    # Return the configured named logger 
    return logger