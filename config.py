"""
Optional[int]
Configuration management for the Telegram File Bot.
Loads settings from environment variables with fallbacks.
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Configuration class for bot settings."""
    
    # Telegram Bot API
    BOT_TOKEN: str
    
    # Telegram MTProto API
    API_ID: int
    API_HASH: str
    
    # Mega.nz credentials
    MEGA_EMAIL: str
    MEGA_PASSWORD: str
    
    # Storage settings
    STORAGE_CHANNEL_ID: str
    TEMP_DIR: str
    MAX_FILE_SIZE: int
    
    # Compression settings
    DEFAULT_COMPRESSION: str
    COMPRESSION_LEVEL: int
    
    def __init__(self):
        # Required Telegram settings
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        
        try:
            self.API_ID = int(os.getenv("API_ID"))
        except (TypeError, ValueError):
            raise ValueError("API_ID environment variable is required and must be an integer")
        
        self.API_HASH = os.getenv("API_HASH")
        if not self.API_HASH:
            raise ValueError("API_HASH environment variable is required")
        
        # Mega.nz credentials
        self.MEGA_EMAIL = os.getenv("MEGA_EMAIL")
        self.MEGA_PASSWORD = os.getenv("MEGA_PASSWORD")
        
        if not self.MEGA_EMAIL or not self.MEGA_PASSWORD:
            raise ValueError("MEGA_EMAIL and MEGA_PASSWORD environment variables are required")
        
        # Optional settings with defaults
        try:
            self.STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID")) if os.getenv("STORAGE_CHANNEL_ID") else None
        except ValueError:
            self.STORAGE_CHANNEL_ID = None
        
        self.TEMP_DIR = os.getenv("TEMP_DIR", "STORAGE_CHANNEL_ID")
        
        try:
            self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "4294967296"))  # 4GB default
        except ValueError:
            self.MAX_FILE_SIZE = 4294967296
        
        self.DEFAULT_COMPRESSION = os.getenv("DEFAULT_COMPRESSION", "zip")
        
        try:
            self.COMPRESSION_LEVEL = int(os.getenv("COMPRESSION_LEVEL", "6"))
        except ValueError:
            self.COMPRESSION_LEVEL = 6
        
        # Ensure temp directory exists
        os.makedirs(self.TEMP_DIR, exist_ok=True)
    
    def validate(self) -> bool:
        """Validate configuration settings."""
        if not all([self.BOT_TOKEN, self.API_ID, self.API_HASH, self.MEGA_EMAIL, self.MEGA_PASSWORD]):
            return False
        
        if self.DEFAULT_COMPRESSION not in ["zip", "gzip", "lzma"]:
            return False
        
        if not 1 <= self.COMPRESSION_LEVEL <= 9:
            return False
        
        return True
    
    def __str__(self) -> str:
        """Return a safe string representation of the config."""
        return f"""Config(
    BOT_TOKEN={'***' if self.BOT_TOKEN else 'Not set'},
    API_ID={self.API_ID if self.API_ID else 'Not set'},
    API_HASH={'***' if self.API_HASH else 'Not set'},
    MEGA_EMAIL={'***' if self.MEGA_EMAIL else 'Not set'},
    STORAGE_CHANNEL_ID={self.STORAGE_CHANNEL_ID},
    TEMP_DIR={self.TEMP_DIR},
    MAX_FILE_SIZE={self.MAX_FILE_SIZE // (1024**3)}GB,
    DEFAULT_COMPRESSION={self.DEFAULT_COMPRESSION},
    COMPRESSION_LEVEL={self.COMPRESSION_LEVEL}
)"""
