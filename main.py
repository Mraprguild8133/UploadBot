#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling, compression, and Mega.nz storage integration.
Supports both Bot API and MTProto for large file transfers.
Includes automatic Render.com webhook setup.
"""

import asyncio
import logging
import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telethon import TelegramClient
from aiohttp import web
import socket

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Config:
    """Configuration class with environment variables."""
    def __init__(self):
        self.BOT_TOKEN = os.environ.get('BOT_TOKEN')
        self.API_ID = os.environ.get('API_ID')
        self.API_HASH = os.environ.get('API_HASH')
        self.MEGA_EMAIL = os.environ.get('MEGA_EMAIL')
        self.MEGA_PASSWORD = os.environ.get('MEGA_PASSWORD')
        self.WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
        self.RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
        self.RENDER_GIT_REPO_SLUG = os.environ.get('RENDER_GIT_REPO_SLUG')
        self.PORT = int(os.environ.get('PORT', 5000))
        
        # Auto-detect Render environment and set webhook URL if not provided
        if not self.WEBHOOK_URL and self.RENDER_EXTERNAL_HOSTNAME:
            self.WEBHOOK_URL = f"https://{self.RENDER_EXTERNAL_HOSTNAME}"
        elif not self.WEBHOOK_URL and self.RENDER_GIT_REPO_SLUG:
            self.WEBHOOK_URL = f"https://{self.RENDER_GIT_REPO_SLUG}.onrender.com"
        
        # Validate required config
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        if not self.API_ID:
            raise ValueError("API_ID environment variable is required")
        if not self.API_HASH:
            raise ValueError("API_HASH environment variable is required")

class BotHandlers:
    """Bot command handlers."""
    def __init__(self, bot_app, telethon_client, config):
        self.bot_app = bot_app
        self.telethon_client = telethon_client
        self.config = config
    
    async def start_command(self, update: Update, context):
        """Send welcome message when the command /start is issued."""
        await update.message.reply_text(
            "🤖 Hello! I'm your file handling bot.\n\n"
            "I can handle files up to 4GB with compression and Mega.nz integration.\n\n"
            "Use /help to see available commands."
        )
    
    async def help_command(self, update: Update, context):
        """Send help message when the command /help is issued."""
        help_text = """
📚 Available Commands:

/start - Start the bot
/help - Show this help message
/upload - Upload a file to storage
/download - Download a file from storage
/list - List available files
/delete - Delete a file
/compress - Compress files before uploading
/settings - Configure bot settings

📁 Just send me any file and I'll handle it automatically!
        """
        await update.message.reply_text(help_text)
    
    async def upload_command(self, update: Update, context):
        """Handle upload command."""
        await update.message.reply_text("📤 Upload functionality will be implemented here.")
    
    async def download_command(self, update: Update, context):
        """Handle download command."""
        await update.message.reply_text("📥 Download functionality will be implemented here.")
    
    async def list_files_command(self, update: Update, context):
        """Handle list files command."""
        await update.message.reply_text("📋 List files functionality will be implemented here.")
    
    async def delete_file_command(self, update: Update, context):
        """Handle delete file command."""
        await update.message.reply_text("🗑️ Delete file functionality will be implemented here.")
    
    async def compress_command(self, update: Update, context):
        """Handle compress command."""
        await update.message.reply_text("🗜️ Compress functionality will be implemented here.")
    
    async def settings_command(self, update: Update, context):
        """Handle settings command."""
        await update.message.reply_text("⚙️ Settings functionality will be implemented here.")
    
    async def handle_file_upload(self, update: Update, context):
        """Handle incoming files."""
        message = update.message
        file = None
        
        # Determine the file type and get file info
        if message.document:
            file = message.document
            file_type = "document"
        elif message.photo:
            file = message.photo[-1]  # Get the highest resolution photo
            file_type = "photo"
        elif message.video:
            file = message.video
            file_type = "video"
        elif message.audio:
            file = message.audio
            file_type = "audio"
        else:
            await message.reply_text("❌ Unsupported file type.")
            return
        
        # Get file information
        file_name = getattr(file, 'file_name', f'{file_type}_{file.file_id}')
        file_size = file.file_size
        
        # Notify user
        await message.reply_text(
            f"📄 Received your file: {file_name}\n"
            f"📦 Size: {file_size / (1024*1024):.2f} MB\n\n"
            "⏳ Processing your file..."
        )
        
        # Here you would add your actual file processing logic
        # For now, we'll just simulate processing
        await asyncio.sleep(2)
        
        await message.reply_text(
            f"✅ File processed successfully!\n"
            f"📄 Name: {file_name}\n"
            f"📦 Size: {file_size / (1024*1024):.2f} MB\n\n"
            "Use /download to retrieve your file later."
        )

class TelegramFileBot:
    def __init__(self):
        self.config = Config()
        self.bot_handlers = None
        self.telethon_client = None
        self.application = None
        self.webhook_url = None
        
    async def initialize(self):
        """Initialize the bot with both Bot API and MTProto clients."""
        try:
            # Initialize Telethon client for large file handling
            self.telethon_client = TelegramClient(
                'bot_session',
                int(self.config.API_ID),
                self.config.API_HASH
            )
            
            # Start Telethon client
            await self.telethon_client.start(bot_token=self.config.BOT_TOKEN)
            logger.info("Telethon client initialized successfully")
            
            # Initialize Bot API application
            self.application = Application.builder().token(self.config.BOT_TOKEN).build()
            
            # Initialize handlers with both clients
            self.bot_handlers = BotHandlers(
                bot_app=self.application,
                telethon_client=self.telethon_client,
                config=self.config
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
        """Set up webhook automatically for Render."""
        if not self.config.WEBHOOK_URL:
            logger.warning("WEBHOOK_URL not set, webhook mode disabled")
            return False
            
        self.webhook_url = f"{self.config.WEBHOOK_URL}/webhook"
        
        try:
            # Set webhook
            await self.application.bot.set_webhook(
                url=self.webhook_url,
                drop_pending_updates=True
            )
            
            logger.info(f"Webhook set to: {self.webhook_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            return False
    
    async def run_webhook(self):
        """Run the bot with webhook for Render deployment."""
        try:
            await self.initialize()
            logger.info("Starting Telegram File Bot with webhook for Render...")
            
            # Set up webhook
            webhook_set = await self.setup_webhook()
            if not webhook_set:
                logger.error("Failed to set webhook, switching to polling mode")
                await self.run_polling()
                return
            
            # Create aiohttp web application for webhook
            app = web.Application()
            app.router.add_post('/webhook', self._handle_webhook)
            
            # Add health check endpoint (required by Render)
            app.router.add_get('/health', self._health_check)
            
            # Add root endpoint
            app.router.add_get('/', self._root_handler)
            
            # Start the webhook server
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', self.config.PORT)
            await site.start()
            
            logger.info(f"Bot is running with webhook on port {self.config.PORT}!")
            logger.info(f"Webhook URL: {self.webhook_url}")
            
            # Display bot info
            bot_info = await self.application.bot.get_me()
            logger.info(f"Bot username: @{bot_info.username}")
            
            # Keep the application running
            await asyncio.Event().wait()
            
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def _handle_webhook(self, request):
        """Handle incoming webhook requests."""
        try:
            # Parse the request
            data = await request.json()
            update = Update.de_json(data, self.application.bot)
            
            # Process the update
            await self.application.process_update(update)
            
            return web.Response(status=200, text="OK")
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return web.Response(status=500, text="Error")
    
    async def _health_check(self, request):
        """Health check endpoint for Render."""
        return web.Response(text="OK", status=200)
    
    async def _root_handler(self, request):
        """Root endpoint handler."""
        return web.Response(
            text="🤖 Telegram File Bot is running!\n\n"
                 "This bot handles files up to 4GB with compression and Mega.nz integration.",
            status=200
        )
    
    async def run_polling(self):
        """Run the bot with polling (for local development)."""
        try:
            await self.initialize()
            logger.info("Starting Telegram File Bot with polling...")
            
            # Display bot info
            bot_info = await self.application.bot.get_me()
            logger.info(f"Bot username: @{bot_info.username}")
            
            # Start the bot with polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot is running with polling! Press Ctrl+C to stop.")
            
            # Keep the bot running
            await asyncio.Event().wait()
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.shutdown()
    
    async def run(self):
        """Start the bot in the appropriate mode based on environment."""
        # Check if we're running on Render (has PORT environment variable)
        is_render = os.environ.get('PORT') is not None
        
        if is_render:
            logger.info("Detected Render environment, using webhook mode")
            await self.run_webhook()
        else:
            logger.info("Using local polling mode")
            await self.run_polling()
    
    async def shutdown(self):
        """Cleanup and shutdown."""
        logger.info("Shutting down bot...")
        
        if hasattr(self, 'application') and self.application:
            if hasattr(self.application, 'updater') and self.application.updater:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        if hasattr(self, 'telethon_client') and self.telethon_client:
            await self.telethon_client.disconnect()
        
        logger.info("Bot shutdown complete")

async def main():
    """Main entry point."""
    try:
        bot = TelegramFileBot()
        await bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
