import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def clean_filename(filename: str) -> str:
    """Clean a string to be used as a filename."""
    # Replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove any double underscores
    while '__' in filename:
        filename = filename.replace('__', '_')
    
    # Remove leading/trailing underscores and dots
    filename = filename.strip('_.')
    
    # Limit length
    return filename[:100]

def ensure_dir_exists(path: str) -> None:
    """Create directory if it doesn't exist."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        raise

def get_unique_filename(path: str, base_name: str, ext: str = '') -> str:
    """Get a unique filename by appending a number if needed."""
    if not ext and '.' in base_name:
        base_name, ext = os.path.splitext(base_name)
    elif ext and not ext.startswith('.'):
        ext = '.' + ext
        
    counter = 1
    filename = f"{base_name}{ext}"
    full_path = os.path.join(path, filename)
    
    while os.path.exists(full_path):
        filename = f"{base_name}_{counter}{ext}"
        full_path = os.path.join(path, filename)
        counter += 1
        
    return filename
