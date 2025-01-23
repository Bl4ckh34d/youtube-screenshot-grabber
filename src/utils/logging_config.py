import logging
import sys

def setup_logging():
    """Configure logging for the application."""
    # Suppress PIL debug logging
    logging.getLogger('PIL').setLevel(logging.INFO)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)
