"""
Utility functions for the Telegram File Bot.
Contains helper functions for file operations, formatting, and ID generation.
"""

import hashlib
import os
import random
import string
import time
from typing import Optional

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 MB", "2.3 GB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    if i == 0:
        return f"{int(size)} {size_names[i]}"
    else:
        return f"{size:.1f} {size_names[i]}"

def calculate_compression_ratio(original_size: int, compressed_size: int) -> float:
    """
    Calculate compression ratio as percentage reduction.
    
    Args:
        original_size: Original file size in bytes
        compressed_size: Compressed file size in bytes
        
    Returns:
        Compression ratio as percentage (0-100)
    """
    if original_size == 0:
        return 0.0
    
    reduction = (original_size - compressed_size) / original_size * 100
    return max(0.0, reduction)

def generate_file_id() -> str:
    """
    Generate a unique file ID.
    
    Returns:
        Unique file identifier string
    """
    timestamp = str(int(time.time()))
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{timestamp}_{random_chars}"

def generate_file_hash(file_path: str) -> str:
    """
    Generate MD5 hash of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for file system
    """
    # Remove invalid characters for most file systems
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = f"file_{int(time.time())}"
    
    return filename

def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.
    
    Args:
        filename: File name
        
    Returns:
        File extension (without dot) or empty string
    """
    try:
        return os.path.splitext(filename)[1][1:].lower()
    except:
        return ""

def is_media_file(filename: str) -> bool:
    """
    Check if file is a media file based on extension.
    
    Args:
        filename: File name
        
    Returns:
        True if media file, False otherwise
    """
    media_extensions = {
        'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'],
        'video': ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm'],
        'audio': ['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a']
    }
    
    extension = get_file_extension(filename)
    
    for media_type, extensions in media_extensions.items():
        if extension in extensions:
            return True
    
    return False

def estimate_compression_size(file_path: str, algorithm: str = 'zip') -> Optional[int]:
    """
    Estimate compressed file size based on file type and algorithm.
    This is a rough estimation for UI purposes.
    
    Args:
        file_path: Path to file
        algorithm: Compression algorithm
        
    Returns:
        Estimated compressed size in bytes or None if cannot estimate
    """
    try:
        original_size = os.path.getsize(file_path)
        extension = get_file_extension(file_path)
        
        # Compression ratios based on file type (rough estimates)
        if extension in ['txt', 'log', 'csv', 'json', 'xml', 'html']:
            # Text files compress very well
            ratio = 0.2 if algorithm == 'lzma' else 0.3 if algorithm == 'gzip' else 0.4
        elif extension in ['jpg', 'png', 'mp3', 'mp4', 'zip', 'rar']:
            # Already compressed files
            ratio = 0.95
        elif extension in ['pdf', 'doc', 'docx']:
            # Document files
            ratio = 0.6 if algorithm == 'lzma' else 0.7 if algorithm == 'gzip' else 0.8
        else:
            # General files
            ratio = 0.5 if algorithm == 'lzma' else 0.6 if algorithm == 'gzip' else 0.7
        
        return int(original_size * ratio)
        
    except:
        return None

def format_duration(seconds: int) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"

def validate_file_type(filename: str, allowed_extensions: Optional[list] = None) -> bool:
    """
    Validate file type based on extension.
    
    Args:
        filename: File name to validate
        allowed_extensions: List of allowed extensions (None = allow all)
        
    Returns:
        True if valid, False otherwise
    """
    if allowed_extensions is None:
        return True
    
    extension = get_file_extension(filename)
    return extension in [ext.lower() for ext in allowed_extensions]

def create_progress_bar(current: int, total: int, width: int = 20) -> str:
    """
    Create a text-based progress bar.
    
    Args:
        current: Current progress value
        total: Total value
        width: Width of progress bar in characters
        
    Returns:
        Progress bar string
    """
    if total == 0:
        return "█" * width
    
    progress = min(current / total, 1.0)
    filled = int(width * progress)
    bar = "█" * filled + "░" * (width - filled)
    percentage = int(progress * 100)
    
    return f"{bar} {percentage}%"

def safe_filename_from_url(url: str) -> str:
    """
    Extract a safe filename from URL.
    
    Args:
        url: URL string
        
    Returns:
        Safe filename
    """
    try:
        # Extract filename from URL
        filename = url.split('/')[-1].split('?')[0]
        
        # If no filename found, generate one
        if not filename or '.' not in filename:
            filename = f"download_{int(time.time())}"
        
        return sanitize_filename(filename)
        
    except:
        return f"download_{int(time.time())}"
