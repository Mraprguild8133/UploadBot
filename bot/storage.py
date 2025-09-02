"""
Cloud storage integration for file upload/download.
Handles file metadata, user file tracking, and link generation.
Note: Using local storage as fallback until Mega.nz library compatibility is resolved.
"""

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
import requests

from .compression import CompressionManager
from .utils import generate_file_id

logger = logging.getLogger(__name__)

class MegaUploader:
    """Handles Mega.nz file uploads as additional cloud storage."""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.mega = None
        
    async def initialize(self):
        """Initialize Mega.nz connection."""
        try:
            # Import mega.py here to avoid errors if not installed
            from mega import Mega
            
            mega = Mega()
            self.mega = mega.login(self.email, self.password)
            logger.info("Mega.nz connection initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"Mega.nz initialization failed: {e}")
            return False
    
    async def upload_file(self, file_path: str, filename: str):
        """Upload file to Mega.nz and return public link."""
        if not self.mega:
            return None
            
        try:
            logger.info(f"Uploading {filename} to Mega.nz...")
            
            # Upload file to Mega
            uploaded_file = self.mega.upload(file_path)
            
            # Get public link
            public_link = self.mega.get_upload_link(uploaded_file)
            
            logger.info(f"File uploaded to Mega.nz successfully: {public_link}")
            return public_link
            
        except Exception as e:
            logger.error(f"Mega.nz upload failed: {e}")
            return None

class MegaStorageManager:
    def __init__(self, config):
        self.config = config
        self.compression_manager = CompressionManager(config)
        self.metadata_file = os.path.join(config.TEMP_DIR, 'file_metadata.json')
        self.metadata = self._load_metadata()
        self.storage_dir = os.path.join(config.TEMP_DIR, 'file_storage')
        os.makedirs(self.storage_dir, exist_ok=True)
        self.telethon_client = None
        self.mega_uploader = MegaUploader(config.MEGA_EMAIL, config.MEGA_PASSWORD) if config.MEGA_EMAIL and config.MEGA_PASSWORD else None
        
    def set_telethon_client(self, client):
        """Set Telethon client for channel storage."""
        self.telethon_client = client
        
    async def initialize(self):
        """Initialize storage system."""
        try:
            # Initialize Mega.nz if configured
            mega_ready = False
            if self.mega_uploader:
                mega_ready = await self.mega_uploader.initialize()
            
            # Log storage configuration
            storage_methods = []
            if self.config.STORAGE_CHANNEL_ID and self.telethon_client:
                storage_methods.append("Telegram Channel")
            if mega_ready:
                storage_methods.append("Mega.nz")
            storage_methods.append("Local Backup")
            
            logger.info(f"Storage system initialized: {', '.join(storage_methods)}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")
            return False
    
    async def upload_file(self, file_path: str, file_id: str, user_id: int, metadata: Dict) -> str:
        """
        Upload a file to storage and store metadata.
        Uses Telegram channel for instant access if configured, with local backup.
        
        Args:
            file_path: Path to file to upload
            file_id: Unique file identifier
            user_id: Telegram user ID
            metadata: File metadata dictionary
            
        Returns:
            Public download link
        """
        try:
            # Try uploading to multiple storage locations
            telegram_message_id = None
            channel_link = None
            mega_link = None
            
            # Upload to Telegram channel for instant access
            if self.config.STORAGE_CHANNEL_ID and self.telethon_client:
                try:
                    logger.info(f"Uploading {file_path} to Telegram channel for instant access")
                    
                    # Upload to storage channel
                    message = await self.telethon_client.send_file(
                        self.config.STORAGE_CHANNEL_ID,
                        file_path,
                        caption=f"File ID: {file_id}\nUser: {user_id}\nOriginal: {metadata.get('original_name', 'unknown')}"
                    )
                    
                    telegram_message_id = message.id
                    channel_link = f"t.me/c/{str(self.config.STORAGE_CHANNEL_ID)[4:]}/{message.id}"
                    logger.info(f"File uploaded to Telegram channel successfully: Message ID {telegram_message_id}")
                    
                except Exception as channel_error:
                    logger.warning(f"Channel upload failed: {channel_error}")
            
            # Also upload to Mega.nz for cloud backup
            if self.mega_uploader and self.mega_uploader.mega:
                try:
                    mega_link = await self.mega_uploader.upload_file(
                        file_path, 
                        metadata.get('original_name', os.path.basename(file_path))
                    )
                    if mega_link:
                        logger.info("File uploaded to Mega.nz successfully")
                except Exception as mega_error:
                    logger.warning(f"Mega.nz upload failed: {mega_error}")
            
            # Always keep local backup
            user_folder = os.path.join(self.storage_dir, f"user_{user_id}")
            os.makedirs(user_folder, exist_ok=True)
            
            stored_file_path = os.path.join(user_folder, f"{file_id}_{os.path.basename(file_path)}")
            logger.info(f"Creating local backup: {stored_file_path}")
            shutil.copy2(file_path, stored_file_path)
            
            # Determine primary download method (prefer Telegram channel for instant access)
            if telegram_message_id:
                public_link = channel_link
                storage_type = "telegram_channel"
            elif mega_link:
                public_link = mega_link
                storage_type = "mega_cloud"
            else:
                public_link = stored_file_path
                storage_type = "local"
            
            # Store metadata with all storage locations
            file_metadata = {
                'file_id': file_id,
                'user_id': user_id,
                'stored_file_path': stored_file_path,
                'telegram_message_id': telegram_message_id,
                'channel_link': channel_link,
                'mega_link': mega_link,
                'public_link': public_link,
                'storage_type': storage_type,
                'upload_date': datetime.now().isoformat(),
                **metadata
            }
            
            await self._store_file_metadata(file_id, file_metadata)
            
            logger.info(f"File uploaded successfully: {file_id} (Storage: {storage_type})")
            return public_link
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise
    
    async def download_and_decompress(self, file_id: str, user_id: int, progress_callback: Optional[Callable] = None) -> Optional[Tuple[str, str, int]]:
        """
        Download and decompress a file from storage.
        Uses Telegram channel for instant download if available, falls back to local.
        
        Args:
            file_id: File identifier
            user_id: Telegram user ID
            progress_callback: Optional progress callback function
            
        Returns:
            Tuple of (decompressed_file_path, original_filename, file_size) or None if not found
        """
        # Get file metadata
        file_metadata = await self._get_file_metadata(file_id, user_id)
        if not file_metadata:
            return None
        
        try:
            if progress_callback:
                await progress_callback(10)
            
            compressed_file_path = None
            
            # Try downloading from Telegram channel first (instant)
            if (file_metadata.get('telegram_message_id') and 
                self.config.STORAGE_CHANNEL_ID and 
                self.telethon_client):
                
                try:
                    logger.info(f"Downloading from Telegram channel (instant): Message ID {file_metadata['telegram_message_id']}")
                    
                    temp_download_path = os.path.join(
                        self.config.TEMP_DIR, 
                        f"channel_download_{file_id}_{int(time.time())}"
                    )
                    
                    # Download from channel
                    await self.telethon_client.download_media(
                        await self.telethon_client.get_messages(
                            self.config.STORAGE_CHANNEL_ID, 
                            ids=file_metadata['telegram_message_id']
                        ),
                        temp_download_path
                    )
                    
                    compressed_file_path = temp_download_path
                    logger.info("Downloaded from Telegram channel successfully")
                    
                    if progress_callback:
                        await progress_callback(60)
                        
                except Exception as channel_error:
                    logger.warning(f"Channel download failed, using local backup: {channel_error}")
            
            # Fall back to local storage if channel download failed
            if not compressed_file_path:
                stored_file_path = file_metadata['stored_file_path']
                
                if not os.path.exists(stored_file_path):
                    raise Exception("File not found in any storage location")
                
                compressed_file_path = stored_file_path
                logger.info("Using local backup file")
                
                if progress_callback:
                    await progress_callback(60)
            
            if progress_callback:
                await progress_callback(80)
            
            # Decompress file
            decompressed_path = await self.compression_manager.decompress_file(compressed_file_path)
            
            if progress_callback:
                await progress_callback(100)
            
            # Return file info
            original_filename = file_metadata['original_name']
            file_size = file_metadata['original_size']
            
            return decompressed_path, original_filename, file_size
            
        except Exception as e:
            logger.error(f"Download/decompress failed: {e}")
            raise
    
    async def list_user_files(self, user_id: int) -> List[Dict]:
        """Get list of files for a user."""
        user_files = []
        
        for file_id, metadata in self.metadata.items():
            if metadata.get('user_id') == user_id:
                user_files.append({
                    'file_id': file_id,
                    'original_name': metadata.get('original_name', 'Unknown'),
                    'original_size': metadata.get('original_size', 0),
                    'compressed_size': metadata.get('compressed_size', 0),
                    'compression_ratio': metadata.get('compression_ratio', 0),
                    'upload_date': metadata.get('upload_date', 'Unknown'),
                    'public_link': metadata.get('public_link', '')
                })
        
        # Sort by upload date (newest first)
        user_files.sort(key=lambda x: x['upload_date'], reverse=True)
        return user_files
    
    async def delete_file(self, file_id: str, user_id: int) -> bool:
        """Delete a file from storage and metadata."""
        file_metadata = await self._get_file_metadata(file_id, user_id)
        if not file_metadata:
            return False
        
        try:
            # Delete from local storage
            stored_file_path = file_metadata.get('stored_file_path')
            if stored_file_path and os.path.exists(stored_file_path):
                os.remove(stored_file_path)
            
            # Remove from metadata
            if file_id in self.metadata:
                del self.metadata[file_id]
                await self._save_metadata()
            
            logger.info(f"File deleted successfully: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
    
    async def get_storage_info(self) -> Dict:
        """Get storage information."""
        try:
            # Calculate local storage usage
            total_size = 0
            file_count = 0
            
            for root, dirs, files in os.walk(self.storage_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                    except OSError:
                        pass
            
            return {
                'storage_type': 'local',
                'total_files': file_count,
                'total_size': total_size,
                'storage_dir': self.storage_dir
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return {}
    
    async def _get_or_create_folder(self, folder_name: str):
        """Get existing folder or create new one."""
        try:
            folder_path = os.path.join(self.storage_dir, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            return folder_path
            
        except Exception as e:
            logger.error(f"Folder operation failed: {e}")
            raise
    
    async def _store_file_metadata(self, file_id: str, metadata: Dict):
        """Store file metadata."""
        self.metadata[file_id] = metadata
        await self._save_metadata()
    
    async def _get_file_metadata(self, file_id: str, user_id: int) -> Optional[Dict]:
        """Get file metadata for a specific user."""
        metadata = self.metadata.get(file_id)
        if metadata and metadata.get('user_id') == user_id:
            return metadata
        return None
    
    def _load_metadata(self) -> Dict:
        """Load metadata from file."""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
        
        return {}
    
    async def _save_metadata(self):
        """Save metadata to file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
        
