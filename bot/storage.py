"""
Cloud storage integration for file upload/download.
Handles file metadata, user file tracking, and link generation.
Uses Telegram channel as primary storage, with local storage as backup.
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

class TelegramChannelManager:
    """Handles Telegram channel file uploads as primary storage."""
    
    def __init__(self, telethon_client, channel_id):
        self.telethon_client = telethon_client
        self.channel_id = channel_id
        self.initialized = False
        
    async def initialize(self):
        """Verify Telegram channel connection."""
        try:
            if self.telethon_client and self.channel_id:
                # Verify we can access the channel
                channel_entity = await self.telethon_client.get_entity(self.channel_id)
                self.initialized = True
                logger.info("Telegram channel storage initialized successfully")
                return True
        except Exception as e:
            logger.error(f"Telegram channel initialization failed: {e}")
            self.initialized = False
        return False
    
    async def upload_file(self, file_path: str, caption: str) -> Optional[Tuple[int, str]]:
        """Upload file to Telegram channel and return message info."""
        if not self.initialized:
            return None
            
        try:
            logger.info(f"Uploading {file_path} to Telegram channel...")
            
            # Upload to storage channel
            message = await self.telethon_client.send_file(
                self.channel_id,
                file_path,
                caption=caption,
                force_document=True  # Ensure files are sent as documents
            )
            
            # Generate public link (format: t.me/c/channel_id/message_id)
            # Remove the -100 prefix from channel ID for the link
            channel_link_id = str(self.channel_id).replace('-100', '')
            channel_link = f"t.me/c/{channel_link_id}/{message.id}"
            
            logger.info(f"File uploaded to Telegram channel successfully: Message ID {message.id}")
            return message.id, channel_link
            
        except Exception as e:
            logger.error(f"Telegram channel upload failed: {e}")
            return None

class TelegramStorageManager:
    def __init__(self, config):
        self.config = config
        self.compression_manager = CompressionManager(config)
        self.metadata_file = os.path.join(config.TEMP_DIR, 'file_metadata.json')
        self.metadata = self._load_metadata()
        self.storage_dir = os.path.join(config.TEMP_DIR, 'file_storage')
        os.makedirs(self.storage_dir, exist_ok=True)
        self.telethon_client = None
        self.channel_manager = None
        
    def set_telethon_client(self, client):
        """Set Telethon client for channel storage."""
        self.telethon_client = client
        if self.config.STORAGE_CHANNEL_ID:
            self.channel_manager = TelegramChannelManager(client, self.config.STORAGE_CHANNEL_ID)
        
    async def initialize(self):
        """Initialize storage system."""
        try:
            # Initialize Telegram channel as primary storage
            telegram_ready = False
            if self.channel_manager:
                telegram_ready = await self.channel_manager.initialize()
            
            # Log storage configuration
            storage_methods = []
            if telegram_ready:
                storage_methods.append("Telegram Channel (Primary)")
            storage_methods.append("Local Storage (Backup)")
            
            logger.info(f"Storage system initialized: {', '.join(storage_methods)}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize storage: {e}")
            return False
    
    async def upload_file(self, file_path: str, file_id: str, user_id: int, metadata: Dict) -> str:
        """
        Upload a file to storage and store metadata.
        Uses Telegram channel as primary storage, with local backup.
        
        Args:
            file_path: Path to file to upload
            file_id: Unique file identifier
            user_id: Telegram user ID
            metadata: File metadata dictionary
            
        Returns:
            Public download link
        """
        try:
            telegram_message_id = None
            channel_link = None
            
            # Try uploading to Telegram channel first (primary)
            if self.channel_manager and self.channel_manager.initialized:
                try:
                    caption = f"File ID: {file_id}\nUser: {user_id}\nOriginal: {metadata.get('original_name', 'unknown')}"
                    
                    result = await self.channel_manager.upload_file(file_path, caption)
                    if result:
                        telegram_message_id, channel_link = result
                        logger.info(f"File uploaded to Telegram channel successfully: Message ID {telegram_message_id}")
                    
                except Exception as channel_error:
                    logger.warning(f"Primary channel upload failed: {channel_error}")
            
            # Always keep local backup regardless of Telegram success
            user_folder = os.path.join(self.storage_dir, f"user_{user_id}")
            os.makedirs(user_folder, exist_ok=True)
            
            stored_file_path = os.path.join(user_folder, f"{file_id}_{os.path.basename(file_path)}")
            logger.info(f"Creating local backup: {stored_file_path}")
            shutil.copy2(file_path, stored_file_path)
            
            # Determine primary download method (prefer Telegram channel)
            if channel_link:
                public_link = channel_link
                storage_type = "telegram_channel"
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
            
            # Try downloading from Telegram channel first (primary)
            if (file_metadata.get('telegram_message_id') and 
                self.config.STORAGE_CHANNEL_ID and 
                self.telethon_client):
                
                try:
                    logger.info(f"Downloading from Telegram channel (primary): Message ID {file_metadata['telegram_message_id']}")
                    
                    temp_download_path = os.path.join(
                        self.config.TEMP_DIR, 
                        f"channel_download_{file_id}_{int(time.time())}"
                    )
                    
                    # Download from channel
                    message = await self.telethon_client.get_messages(
                        self.config.STORAGE_CHANNEL_ID, 
                        ids=file_metadata['telegram_message_id']
                    )
                    
                    if message and message.media:
                        await self.telethon_client.download_media(
                            message,
                            temp_download_path
                        )
                        
                        if os.path.exists(temp_download_path):
                            compressed_file_path = temp_download_path
                            logger.info("Downloaded from Telegram channel successfully")
                            
                            if progress_callback:
                                await progress_callback(60)
                        else:
                            logger.warning("Telegram download failed - file not found after download")
                    else:
                        logger.warning("Telegram message or media not found")
                        
                except Exception as channel_error:
                    logger.warning(f"Channel download failed: {channel_error}")
            
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
            
            # Clean up temporary download file if we used Telegram channel
            if compressed_file_path != file_metadata['stored_file_path']:
                try:
                    os.remove(compressed_file_path)
                except:
                    pass
            
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
                    'public_link': metadata.get('public_link', ''),
                    'storage_type': metadata.get('storage_type', 'unknown')
                })
        
        # Sort by upload date (newest first)
        user_files.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
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
            
            # Try to delete from Telegram channel if message ID exists
            telegram_message_id = file_metadata.get('telegram_message_id')
            if (telegram_message_id and 
                self.config.STORAGE_CHANNEL_ID and 
                self.telethon_client):
                
                try:
                    await self.telethon_client.delete_messages(
                        self.config.STORAGE_CHANNEL_ID,
                        [telegram_message_id]
                    )
                    logger.info(f"Deleted from Telegram channel: Message ID {telegram_message_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete from Telegram channel: {e}")
            
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
            
            # Get Telegram channel info if available
            telegram_info = {}
            if self.channel_manager and self.channel_manager.initialized:
                try:
                    # This is a simplified approach - in a real implementation
                    # you might want to count messages in the channel
                    telegram_info = {
                        'channel_id': self.config.STORAGE_CHANNEL_ID,
                        'status': 'connected'
                    }
                except:
                    telegram_info = {'status': 'error_getting_info'}
            
            return {
                'local_storage': {
                    'total_files': file_count,
                    'total_size': total_size,
                    'storage_dir': self.storage_dir
                },
                'telegram_channel': telegram_info,
                'total_files_in_metadata': len(self.metadata)
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
