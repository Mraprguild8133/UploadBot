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
import time
from aiohttp import web
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.ext import ContextTypes
from telegram import Update
from telethon import TelegramClient, errors
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
        self.max_retries = 5
        self.retry_delay = 10  # seconds
        
    async def initialize_telethon(self):
        """Initialize Telethon client with retry logic."""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting to initialize Telethon client (attempt {attempt + 1}/{self.max_retries})")
                
                self.telethon_client = TelegramClient(
                    'bot_session',
                    self.config.API_ID,
                    self.config.API_HASH,
                    timeout=30,
                    connection_retries=3
                )
                
                # Start Telethon client with timeout
                await asyncio.wait_for(
                    self.telethon_client.start(bot_token=self.config.BOT_TOKEN),
                    timeout=30
                )
                
                logger.info("Telethon client initialized successfully")
                return True
                
            except (errors.ConnectionError, asyncio.TimeoutError, errors.RPCError) as e:
                logger.error(f"Telethon initialization failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error("Max retries exceeded for Telethon initialization")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error during Telethon initialization: {e}")
                return False
                
        return False
        
    async def initialize_bot_api(self):
        """Initialize Bot API application with retry logic."""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempting to initialize Bot API (attempt {attempt + 1}/{self.max_retries})")
                
                # Initialize Bot API application with connection pool size
                self.application = (
                    Application.builder()
                    .token(self.config.BOT_TOKEN)
                    .pool_timeout(30)
                    .read_timeout(30)
                    .write_timeout(30)
                    .build()
                )
                
                # Test connection
                bot = await self.application.bot.get_me()
                logger.info(f"Bot API initialized successfully. Bot: @{bot.username}")
                return True
                
            except Exception as e:
                logger.error(f"Bot API initialization failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error("Max retries exceeded for Bot API initialization")
                    return False
                    
        return False
        
    async def initialize_web_server(self):
        """Initialize web server for port 5000."""
        try:
            self.web_app = web.Application()
            self.web_app.router.add_get('/', self.handle_web_request)
            self.web_app.router.add_get('/health', self.handle_health_check)
            logger.info("Web server initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Web server initialization failed: {e}")
            return False
    
    async def handle_web_request(self, request):
        """Handle web requests to keep the bot alive on hosting platforms."""
        return web.Response(text="Bot is running!")
    
    async def handle_health_check(self, request):
        """Health check endpoint for monitoring."""
        status = {
            "status": "healthy",
            "timestamp": time.time(),
            "telethon_connected": self.telethon_client is not None and self.telethon_client.is_connected(),
            "bot_api_connected": self.application is not None and self.application.running
        }
        return web.json_response(status)
        
    async def initialize_handlers(self):
        """Initialize bot handlers."""
        try:
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
            return True
            
        except Exception as e:
            logger.error(f"Handler initialization failed: {e}")
            return False
    
    async def run(self):
        """Start the bot with web server on port 5000."""
        try:
            logger.info("Starting Telegram File Bot...")
            
            # Initialize components with retry logic
            telethon_success = await self.initialize_telethon()
            bot_api_success = await self.initialize_bot_api()
            web_server_success = await self.initialize_web_server()
            
            if not (telethon_success and bot_api_success):
                logger.error("Failed to initialize Telegram clients. Exiting.")
                return
                
            # Initialize handlers
            if not await self.initialize_handlers():
                logger.error("Failed to initialize handlers. Exiting.")
                return
            
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
        
        if self.application and self.application.running:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        if self.telethon_client and self.telethon_client.is_connected():
            await self.telethon_client.disconnect()
            
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("Bot shutdown complete")

async def main():
    """Main entry point."""
    bot = TelegramFileBot()
    await bot.run()

if __name__ == "__main__":
    # Set event loop policy for Windows compatibility
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the bot
    asyncio.run(main())
