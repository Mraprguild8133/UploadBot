"""
Telegram bot command and message handlers.
Manages user interactions, file processing, and bot responses.
"""

import asyncio
import logging
import os
import time
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename

from .compression import CompressionManager
from .storage import MegaStorageManager
from .utils import format_file_size, calculate_compression_ratio, generate_file_id

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self, bot_app, telethon_client: TelegramClient, config):
        self.bot_app = bot_app
        self.telethon_client = telethon_client
        self.config = config
        self.compression_manager = CompressionManager(config)
        self.storage_manager = MegaStorageManager(config)
        self.storage_manager.set_telethon_client(telethon_client)  # Enable channel storage
        self.active_uploads = {}
        self.user_settings = {}  # Store per-user compression preferences
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_text = """🤖 Welcome to Telegram File Bot!

I can help you:
• Upload files up to 4GB with compression
• Store files locally with compression  
• Download and decompress files
• Manage your uploaded files

Commands:
/upload - Upload a file (or just send me any file)
/download file_id - Download a file by ID
/list - Show your uploaded files
/compress algorithm - Set compression preference
/settings - View current settings
/help - Show detailed help

Supported compression: ZIP, GZIP, LZMA
File size limit: 4GB per file

Just send me any file to get started! 📁"""
        
        keyboard = [
            [InlineKeyboardButton("📋 List Files", callback_data="list_files")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """📖 Detailed Help

File Upload:
• Send any file directly to the bot
• Files are automatically compressed using your preferred algorithm
• Compressed files are stored locally
• You'll receive a file ID and download link

Commands:

/upload - Start file upload mode
/download file_id - Download file by ID
/list - Show all your uploaded files
/delete file_id - Delete a file
/compress algorithm - Set compression (zip/gzip/lzma)
/settings - View current settings

File Size Limits:
• Standard files: Up to 50MB via Bot API
• Large files: Up to 4GB via MTProto
• Automatic method selection based on file size

Compression Options:
• ZIP: Best compatibility, moderate compression
• GZIP: Fast compression, good for text files
• LZMA: Maximum compression, slower processing

File Management:
• Each uploaded file gets a unique ID
• Files are stored compressed locally
• Original filename and metadata preserved
• Compression ratio reported for each file

Tips:
• Use ZIP compression for mixed content
• Use LZMA for maximum space savings
• Use GZIP for quick compression of text files
• Check /settings to view your current preferences

Need more help? Contact the bot administrator."""
        
        await update.message.reply_text(help_text)
    
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upload command."""
        user_id = update.effective_user.id
        
        await update.message.reply_text(
            f"📤 Upload Mode Active\n\n"
            f"Send me any file and I'll compress it and store it locally.\n\n"
            f"Supported formats: Documents, Images, Videos, Audio\n"
            f"Max size: {format_file_size(self.config.MAX_FILE_SIZE)}\n"
            f"Current compression: {self.user_settings.get(user_id, {}).get('compression', self.config.DEFAULT_COMPRESSION).upper()}"
        )
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /download command."""
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a file ID.\n\n"
                "Usage: `/download <file_id>`\n"
                "Use /list to see your uploaded files.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        file_id = context.args[0]
        user_id = update.effective_user.id
        
        # Show download progress message
        progress_msg = await update.message.reply_text("🔄 Starting download...")
        
        try:
            # Download from Mega.nz and decompress
            result = await self.storage_manager.download_and_decompress(
                file_id, user_id, progress_callback=lambda p: self._update_progress(progress_msg, f"📥 Downloading: {p}%")
            )
            
            if not result:
                await progress_msg.edit_text("❌ File not found or download failed.")
                return
            
            decompressed_path, original_filename, file_size = result
            
            # Send file back to user
            await progress_msg.edit_text("📤 Sending file to you...")
            
            # Use appropriate method based on file size
            if file_size < 50 * 1024 * 1024:  # 50MB - use Bot API
                with open(decompressed_path, 'rb') as file:
                    await update.message.reply_document(
                        document=file,
                        filename=original_filename,
                        caption=f"📁 **{original_filename}**\nSize: {format_file_size(file_size)}"
                    )
            else:
                # Use Telethon for large files
                await self.telethon_client.send_file(
                    update.effective_chat.id,
                    decompressed_path,
                    caption=f"📁 **{original_filename}**\nSize: {format_file_size(file_size)}",
                    attributes=[DocumentAttributeFilename(file_name=original_filename)]
                )
            
            await progress_msg.delete()
            
            # Cleanup temp file
            try:
                os.remove(decompressed_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            await progress_msg.edit_text(f"❌ Download failed: {str(e)}")
    
    async def list_files_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command."""
        user_id = update.effective_user.id
        
        try:
            files = await self.storage_manager.list_user_files(user_id)
            
            if not files:
                await update.message.reply_text(
                    "📭 **No files found**\n\n"
                    "You haven't uploaded any files yet.\n"
                    "Send me a file to get started!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            files_text = "📋 Your Files:\n\n"
            for file_info in files[:10]:  # Show max 10 files
                # Determine storage icon based on type
                storage_type = file_info.get('storage_type', 'local')
                if storage_type == 'telegram_channel':
                    storage_icon = "⚡"
                elif storage_type == 'mega_cloud':
                    storage_icon = "☁️"
                else:
                    storage_icon = "💾"
                
                files_text += (
                    f"📁 {file_info['file_id']}\n"
                    f"{file_info['original_name']}\n"
                    f"Size: {format_file_size(file_info['original_size'])} → "
                    f"{format_file_size(file_info['compressed_size'])}\n"
                    f"Compression: {file_info['compression_ratio']:.1f}%\n"
                    f"Storage: {storage_icon} {storage_type.replace('_', ' ').title()}\n"
                    f"Uploaded: {file_info['upload_date'][:10]}\n\n"
                )
            
            if len(files) > 10:
                files_text += f"... and {len(files) - 10} more files\n"
            
            files_text += "\nUse `/download <file_id>` to download a file."
            
            await update.message.reply_text(files_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"List files error: {e}")
            await update.message.reply_text("❌ Failed to retrieve file list.")
    
    async def delete_file_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /delete command."""
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a file ID.\n\n"
                "Usage: `/delete <file_id>`\n"
                "Use /list to see your uploaded files.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        file_id = context.args[0]
        user_id = update.effective_user.id
        
        try:
            success = await self.storage_manager.delete_file(file_id, user_id)
            
            if success:
                await update.message.reply_text(f"✅ File `{file_id}` deleted successfully.", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("❌ File not found or deletion failed.")
                
        except Exception as e:
            logger.error(f"Delete file error: {e}")
            await update.message.reply_text("❌ Failed to delete file.")
    
    async def compress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /compress command."""
        if not context.args:
            await update.message.reply_text(
                "⚙️ **Compression Settings**\n\n"
                "Available algorithms:\n"
                "• `zip` - Best compatibility, moderate compression\n"
                "• `gzip` - Fast compression, good for text\n"
                "• `lzma` - Maximum compression, slower\n\n"
                "Usage: `/compress <algorithm>`\n"
                "Example: `/compress lzma`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        algorithm = context.args[0].lower()
        if algorithm not in ["zip", "gzip", "lzma"]:
            await update.message.reply_text(
                "❌ Invalid compression algorithm.\n"
                "Supported: zip, gzip, lzma",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        user_id = update.effective_user.id
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {}
        
        self.user_settings[user_id]['compression'] = algorithm
        
        await update.message.reply_text(
            f"✅ Compression algorithm set to **{algorithm.upper()}**\n\n"
            f"All future uploads will use {algorithm} compression.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command."""
        user_id = update.effective_user.id
        user_prefs = self.user_settings.get(user_id, {})
        
        settings_text = f"""
⚙️ **Your Settings**

**Compression Algorithm:** {user_prefs.get('compression', self.config.DEFAULT_COMPRESSION).upper()}
**Compression Level:** {self.config.COMPRESSION_LEVEL}/9
**Max File Size:** {format_file_size(self.config.MAX_FILE_SIZE)}
**Temp Directory:** {self.config.TEMP_DIR}

**Storage:**
• Mega.nz Account: Connected ✅
• Telegram Channel: {'Connected' if self.config.STORAGE_CHANNEL_ID else 'Not configured'}

**Usage Tips:**
• ZIP: Best for mixed file types
• GZIP: Fastest compression
• LZMA: Best compression ratio

Use `/compress <algorithm>` to change compression.
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 My Files", callback_data="list_files")],
            [InlineKeyboardButton("🗜️ ZIP", callback_data="compress_zip")],
            [InlineKeyboardButton("⚡ GZIP", callback_data="compress_gzip")],
            [InlineKeyboardButton("🎯 LZMA", callback_data="compress_lzma")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            settings_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle file uploads from users."""
        user_id = update.effective_user.id
        
        # Check if file is provided
        file_obj = None
        if update.message.document:
            file_obj = update.message.document
            file_type = "document"
        elif update.message.photo:
            file_obj = update.message.photo[-1]  # Get highest resolution
            file_type = "photo"
        elif update.message.video:
            file_obj = update.message.video
            file_type = "video"
        elif update.message.audio:
            file_obj = update.message.audio
            file_type = "audio"
        else:
            await update.message.reply_text("❌ Please send a valid file.")
            return
        
        # Check file size
        if file_obj.file_size > self.config.MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ File too large! Maximum size: {format_file_size(self.config.MAX_FILE_SIZE)}\n"
                f"Your file: {format_file_size(file_obj.file_size)}"
            )
            return
        
        # Get filename
        if hasattr(file_obj, 'file_name') and file_obj.file_name:
            original_filename = file_obj.file_name
        elif file_type == "photo":
            original_filename = f"photo_{int(time.time())}.jpg"
        elif file_type == "video":
            original_filename = f"video_{int(time.time())}.mp4"
        elif file_type == "audio":
            original_filename = f"audio_{int(time.time())}.mp3"
        else:
            original_filename = f"file_{int(time.time())}"
        
        # Show initial progress
        progress_msg = await update.message.reply_text(
            f"📤 **Processing: {original_filename}**\n"
            f"Size: {format_file_size(file_obj.file_size)}\n"
            f"Status: Downloading from Telegram..."
        )
        
        try:
            # Download file from Telegram
            if file_obj.file_size < 20 * 1024 * 1024:  # 20MB - use Bot API
                telegram_file = await context.bot.get_file(file_obj.file_id)
                temp_path = os.path.join(self.config.TEMP_DIR, f"temp_{user_id}_{int(time.time())}")
                await telegram_file.download_to_drive(temp_path)
            else:
                # Use Telethon for larger files
                temp_path = os.path.join(self.config.TEMP_DIR, f"temp_{user_id}_{int(time.time())}")
                await self.telethon_client.download_media(
                    await self.telethon_client.get_messages(update.effective_chat.id, ids=update.message.message_id),
                    temp_path
                )
            
            await progress_msg.edit_text(
                f"📤 **Processing: {original_filename}**\n"
                f"Size: {format_file_size(file_obj.file_size)}\n"
                f"Status: Compressing file..."
            )
            
            # Compress file
            compression_algo = self.user_settings.get(user_id, {}).get('compression', self.config.DEFAULT_COMPRESSION)
            compressed_path = await self.compression_manager.compress_file(
                temp_path, compression_algo, self.config.COMPRESSION_LEVEL
            )
            
            # Calculate compression ratio
            compressed_size = os.path.getsize(compressed_path)
            compression_ratio = calculate_compression_ratio(file_obj.file_size, compressed_size)
            
            await progress_msg.edit_text(
                f"📤 **Processing: {original_filename}**\n"
                f"Original: {format_file_size(file_obj.file_size)}\n"
                f"Compressed: {format_file_size(compressed_size)} ({compression_ratio:.1f}% reduction)\n"
                f"Status: Uploading to Mega.nz..."
            )
            
            # Upload to Mega.nz
            file_id = generate_file_id()
            mega_link = await self.storage_manager.upload_file(
                compressed_path, file_id, user_id, {
                    'original_name': original_filename,
                    'original_size': file_obj.file_size,
                    'compressed_size': compressed_size,
                    'compression_algo': compression_algo,
                    'compression_ratio': compression_ratio,
                    'file_type': file_type
                }
            )
            
            # Success message
            storage_methods = []
            if self.config.STORAGE_CHANNEL_ID:
                storage_methods.append("⚡ Telegram Channel")
            if self.config.MEGA_EMAIL and self.config.MEGA_PASSWORD:
                storage_methods.append("☁️ Mega.nz")
            storage_methods.append("💾 Local Backup")
            storage_info = " + ".join(storage_methods)
                
            success_text = f"""✅ Upload Complete!

📁 File: {original_filename}
🆔 ID: {file_id}
📊 Size: {format_file_size(file_obj.file_size)} → {format_file_size(compressed_size)}
🗜️ Compression: {compression_ratio:.1f}% reduction ({compression_algo.upper()})
🔗 Storage: {storage_info}

Commands:
• /download {file_id} - Download file
• /delete {file_id} - Delete file
• /list - View all files"""
            
            await progress_msg.edit_text(success_text)
            
            # Cleanup temp files
            for temp_file in [temp_path, compressed_path]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"File upload error: {e}")
            await progress_msg.edit_text(f"❌ Upload failed: {str(e)}")
            
            # Cleanup on error
            for temp_file in [temp_path, compressed_path] if 'compressed_path' in locals() else [temp_path] if 'temp_path' in locals() else []:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
    
    async def _update_progress(self, message, text):
        """Update progress message safely."""
        try:
            await message.edit_text(text)
        except:
            pass  # Ignore edit errors
