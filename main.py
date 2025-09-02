#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling, compression, and Mega.nz storage integration.
Supports both Bot API and MTProto for large file transfers.
Includes web server for port 5000 support on hosting platforms.
"""

import asyncio
import logging
import os
import aiohttp
from aiohttp import web
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telethon import TelegramClient
from config import Config
from bot.handlers import BotHandlers

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramFileBot:
    def __init__(self):
        self.config = Config()
        self.bot_handlers = None
        self.telethon_client = None
        self.application = None
        self.web_app = None
        self.runner = None
        self.site = None
        
    async def initialize(self):
        """Initialize the bot with both Bot API and MTProto clients."""
        try:
            # Initialize Telethon client for large file handling
            self.telethon_client = TelegramClient(
                'bot_session',
                self.config.API_ID,
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
            
            # Initialize web application for port 5000
            self.web_app = web.Application()
            self.web_app.router.add_get('/', self.handle_web_request)
            
            logger.info("Bot handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def handle_web_request(self, request):
        """Handle web requests to keep the bot alive on hosting platforms."""
        return web.Response(text="Bot is running!")
    
    async def run(self):
        """Start the bot with web server on port 5000."""
        try:
            await self.initialize()
            logger.info("Starting Telegram File Bot...")
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            # Start web server on port 5000
            port = int(os.environ.get('PORT', 5000))
            self.runner = web.AppRunner(self.web_app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', port)
            await self.site.start()
            
            logger.info(f"Bot is running! Web server started on port {port}")
            logger.info("Press Ctrl+C to stop.")
            
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
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        if self.telethon_client:
            await self.telethon_client.disconnect()
            
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("Bot shutdown complete")

async def main():
    """Main entry point."""
    bot = TelegramFileBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
