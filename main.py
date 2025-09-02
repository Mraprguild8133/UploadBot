#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling, compression, and Mega.nz storage integration.
Supports both Bot API and MTProto for large file transfers.
Webhook support for Render deployment (port 5000) with fallback to polling mode.
"""

import asyncio
import logging
import os
import aiohttp
from pathlib import Path
from typing import Optional, Dict, Any
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update, Bot, File
from telegram.request import HTTPXRequest
from telethon import TelegramClient, events
from mega import Mega
import zipfile
import io
import tempfile
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Config:
    """Configuration class for the bot."""
    def __init__(self):
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.API_ID = int(os.getenv('API_ID', 0))
        self.API_HASH = os.getenv('API_HASH')
        self.MEGA_EMAIL = os.getenv('MEGA_EMAIL')
        self.MEGA_PASSWORD = os.getenv('MEGA_PASSWORD')
        self.MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB
        self.DOWNLOAD_PATH = os.getenv('DOWNLOAD_PATH', 'downloads')
        self.SESSION_PATH = os.getenv('SESSION_PATH', 'sessions')
        self.WEBHOOK_URL = os.getenv('WEBHOOK_URL')
        self.WEBHOOK_PORT = int(os.getenv('PORT', 5000))  # Render uses port 5000
        self.USE_WEBHOOK = os.getenv('USE_WEBHOOK', 'false').lower() == 'true'
        
        # Validate required environment variables
        if not all([self.BOT_TOKEN, self.API_ID, self.API_HASH]):
            raise ValueError("Missing required environment variables: BOT_TOKEN, API_ID, API_HASH")

        # Get port from environment (for Render.com deployment)
    PORT = int(os.environ.get("PORT", 5000))
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
        # Create necessary directories
        Path(self.DOWNLOAD_PATH).mkdir(exist_ok=True)
        Path(self.SESSION_PATH).mkdir(exist_ok=True)

class MegaStorage:
    """Handler for Mega.nz storage operations."""
    def __init__(self, email: str, pass
                 word: str):
        self.email = email
        self.password = password
        self.mega = Mega()
        self.logged_in = False
        
    async def login(self):
        """Login to Mega.nz account."""
        try:
            if not self.email or not self.password:
                raise ValueError("MEGA_EMAIL and MEGA_PASSWORD environment variables are required for Mega.nz integration")
            
            # Run blocking Mega login in executor thread
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.mega.login, self.email, self.password)
            self.logged_in = True
            logger.info("Successfully logged in to Mega.nz")
        except Exception as e:
            logger.error(f"Failed to login to Mega.nz: {e}")
            raise

    async def upload_file(self, file_path: str, file_name: Optional[str] = None) -> Optional[str]:
        """Upload a file to Mega.nz and return the download URL."""
        if not self.logged_in:
            await self.login()
        
        try:
            if not file_name:
                file_name = os.path.basename(file_path)
            
            # Run blocking Mega upload in executor thread
            loop = asyncio.get_event_loop()
            file = await loop.run_in_executor(None, self.mega.upload, file_path, None, file_name)
            download_url = await loop.run_in_executor(None, self.mega.get_upload_link, file)
            
            logger.info(f"File uploaded to Mega.nz: {download_url}")
            return download_url
        except Exception as e:
            logger.error(f"Failed to upload file to Mega.nz: {e}")
            return None

    async def download_file(self, url: str, download_path: Optional[str] = None) -> Optional[str]:
        """Download a file from Mega.nz."""
        if not self.logged_in:
            await self.login()
        
        try:
            # Run blocking Mega download in executor thread
            loop = asyncio.get_event_loop()
            file_path = await loop.run_in_executor(None, self.mega.download_url, url, download_path)
            
            logger.info(f"File downloaded from Mega.nz: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to download file from Mega.nz: {e}")
            return None

class BotHandlers:
    """Handlers for Telegram bot commands and messages."""
    def __init__(self, bot_app: Application, telethon_client: TelegramClient, config: Config, mega_storage: MegaStorage):
        self.bot_app = bot_app
        self.telethon_client = telethon_client
        self.config = config
        self.mega_storage = mega_storage
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a welcome message when the command /start is issued."""
        user = update.effective_user
        await update.message.reply_text(
            f"Hi {user.mention_html()}! 👋\n\n"
            "I'm a file handling bot with support for large files up to 4GB. "
            "I can help you store, compress, and manage your files with Mega.nz integration.\n\n"
            "Use /help to see all available commands.",
            parse_mode="HTML"
        )
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a help message when the command /help is issued."""
        help_text = (
            "📚 <b>Available Commands:</b>\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/upload - Upload a file to Mega.nz\n"
            "/download - Download a file from Mega.nz\n"
            "/list - List your files on Mega.nz\n"
            "/delete - Delete a file from Mega.nz\n"
            "/compress - Compress files before uploading\n"
            "/settings - Configure your preferences\n\n"
            "You can also just send me any file and I'll upload it to Mega.nz automatically!"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
        
    async def upload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /upload command."""
        await update.message.reply_text(
            "Please send me the file you want to upload to Mega.nz. "
            "I can handle files up to 4GB in size!"
        )
        
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /download command."""
        if not context.args:
            await update.message.reply_text(
                "Please provide a Mega.nz URL to download. Usage:\n"
                "/download <mega_url>"
            )
            return
            
        mega_url = context.args[0]
        await update.message.reply_text(f"Starting download from: {mega_url}")
        
        # Download the file
        file_path = await self.mega_storage.download_file(mega_url, self.config.DOWNLOAD_PATH)
        
        if file_path:
            # Send the file to the user
            try:
                with open(file_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        caption="Here's your downloaded file!"
                    )
            except Exception as e:
                await update.message.reply_text(f"Failed to send file: {e}")
        else:
            await update.message.reply_text("Failed to download the file. Please check the URL and try again.")
            
    async def list_files_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /list command."""
        await update.message.reply_text(
            "File listing functionality will be implemented soon. "
            "For now, you can upload files by sending them directly to me!"
        )
        
    async def delete_file_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /delete command."""
        await update.message.reply_text(
            "File deletion functionality will be implemented soon. "
            "Please check back later!"
        )
        
    async def compress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /compress command."""
        await update.message.reply_text(
            "File compression functionality will be implemented soon. "
            "For now, I'll upload files without compression."
        )
        
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /settings command."""
        await update.message.reply_text(
            "Settings functionality will be implemented soon. "
            "Currently using default settings."
        )
        
    async def handle_file_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming files and upload them to Mega.nz."""
        user = update.effective_user
        message = update.message
        
        # Check if the message contains a document, photo, video, or audio
        if message.document:
            file = message.document
        elif message.photo:
            file = message.photo[-1]  # Get the highest resolution photo
        elif message.video:
            file = message.video
        elif message.audio:
            file = message.audio
        else:
            await message.reply_text("Unsupported file type.")
            return
            
        # Check file size
        if file.file_size > self.config.MAX_FILE_SIZE:
            await message.reply_text(
                f"File is too large. Maximum size is {self.config.MAX_FILE_SIZE / (1024**3):.2f} GB."
            )
            return
            
        # Notify user that upload is starting
        status_msg = await message.reply_text(
            f"📤 Downloading your file ({file.file_size / (1024**2):.2f} MB)..."
        )
        
        try:
            # Download the file
            file_path = os.path.join(self.config.DOWNLOAD_PATH, file.file_name or f"file_{file.file_id}")
            
            # Use Telethon for larger files if available
            if file.file_size > 20 * 1024 * 1024 and self.telethon_client.is_connected():
                # Use Telethon for larger files
                async with self.telethon_client.action(user.id, 'document') as action:
                    await message.download_to_drive(file_path)
            else:
                # Use standard bot API for smaller files
                file_obj = await file.get_file()
                await file_obj.download_to_drive(file_path)
                
            # Update status
            await status_msg.edit_text("📤 Uploading to Mega.nz...")
            
            # Upload to Mega.nz
            mega_url = await self.mega_storage.upload_file(file_path, file.file_name)
            
            if mega_url:
                await status_msg.edit_text(
                    f"✅ File successfully uploaded to Mega.nz!\n\n"
                    f"📁 File: {file.file_name or 'Unnamed'}\n"
                    f"📦 Size: {file.file_size / (1024**2):.2f} MB\n"
                    f"🔗 Download URL: {mega_url}"
                )
            else:
                await status_msg.edit_text("❌ Failed to upload file to Mega.nz. Please try again later.")
                
        except Exception as e:
            logger.error(f"Error handling file upload: {e}")
            await status_msg.edit_text(f"❌ An error occurred: {str(e)}")
            
        finally:
            # Clean up downloaded file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error cleaning up file: {e}")

class TelegramFileBot:
    def __init__(self):
        self.config = Config()
        self.bot_handlers = None
        self.telethon_client = None
        self.application = None
        self.mega_storage = None
        
    async def initialize(self):
        """Initialize the bot with both Bot API and MTProto clients."""
        try:
            # Initialize Mega.nz storage
            if self.config.MEGA_EMAIL and self.config.MEGA_PASSWORD:
                self.mega_storage = MegaStorage(self.config.MEGA_EMAIL, self.config.MEGA_PASSWORD)
                await self.mega_storage.login()
            else:
                logger.warning("Mega.nz credentials not provided. Mega.nz functionality will be disabled.")
                self.mega_storage = None
            
            # Initialize Telethon client for large file handling
            session_path = os.path.join(self.config.SESSION_PATH, 'bot_session')
            self.telethon_client = TelegramClient(
                session_path,
                self.config.API_ID,
                self.config.API_HASH
            )
            
            # Start Telethon client
            await self.telethon_client.start(bot_token=self.config.BOT_TOKEN)
            logger.info("Telethon client initialized successfully")
            
            # Initialize Bot API application with custom settings for large files
            request = HTTPXRequest(connection_pool_size=100, read_timeout=30, write_timeout=30, connect_timeout=30)
            self.application = (
                Application.builder()
                .token(self.config.BOT_TOKEN)
                .request(request)
                .build()
            )
            
            # Initialize handlers with both clients
            self.bot_handlers = BotHandlers(
                bot_app=self.application,
                telethon_client=self.telethon_client,
                config=self.config,
                mega_storage=self.mega_storage
            )
            
            # Register command handlers
            self.application.add_handler(CommandHandler("start", self.bot_handlers.start_command))
            self.application.add_handler(CommandHandler("help", self.bot_handlers.help_command))
            self.application.add_handler(CommandHandler("upload", self.bot_handlers.upload_command))
            self.application.add_handler(CommandHandler("download", self.bot_handlers.download_command))
            self.application.add_handler(CommandHandler("list", self.bot_handlers.list_files_command))
            self.application.add_handler(CommandHandler("delete", self.bot_handlers.delete_file_command))
            self.application.add_handler(CommandHandler("compress", self.bot_handlers.compress_command))
            self.application.add_handler(CommandHandler("settings", self.bot_handlers.settings_command))
            
            # Handle file uploads
            self.application.add_handler(MessageHandler(
                filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
                self.bot_handlers.handle_file_upload
            ))
            
            logger.info("Bot handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def setup_webhook(self):
        """Set up webhook for Render deployment."""
        webhook_url = f"{self.config.WEBHOOK_URL}/{self.config.BOT_TOKEN}"
        
        await self.application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info(f"Webhook set to: {webhook_url}")
    
    async def run_polling(self):
        """Run the bot in polling mode (for development)."""
        logger.info("Starting bot in polling mode...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    
    async def run_webhook(self):
        """Run the bot in webhook mode (for production)."""
        logger.info("Starting bot in webhook mode...")
        
        # Set up webhook
        await self.setup_webhook()
        
        # Start the application without the updater
        await self.application.initialize()
        await self.application.start()
        
        # Create aiohttp web application for webhook
        from aiohttp import web
        
        async def handle_webhook(request):
            """Handle incoming webhook updates."""
            data = await request.json()
            update = Update.de_json(data, self.application.bot)
            await self.application.process_update(update)
            return web.Response(status=200)
        
        app = web.Application()
        app.router.add_post(f'/{self.config.BOT_TOKEN}', handle_webhook)
        
        # Start the web server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.config.WEBHOOK_PORT)
        await site.start()
        
        logger.info(f"Webhook server started on port {self.config.WEBHOOK_PORT}")
    
    async def run(self):
        """Start the bot in the appropriate mode."""
        try:
            await self.initialize()
            
            if self.config.USE_WEBHOOK and self.config.WEBHOOK_URL:
                await self.run_webhook()
            else:
                await self.run_polling()
            
            logger.info("Bot is running! Press Ctrl+C to stop.")
            
            # Keep the bot running
            while True:
                await asyncio.sleep(3600)  # Sleep for 1 hour
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Cleanup and shutdown."""
        logger.info("Shutting down bot...")
        
        if self.application:
            if self.application.updater:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        if self.telethon_client:
            await self.telethon_client.disconnect()
        
        logger.info("Bot shutdown complete")

async def main():
    """Main entry point."""
    bot = TelegramFileBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
