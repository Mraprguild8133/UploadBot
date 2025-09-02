#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling, compression, and Mega.nz storage integration.
Supports both Bot API and MTProto for large file transfers.
Includes web server for health checks and deployment platforms.
"""

import asyncio
import logging
import os
import signal
from typing import Optional
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
        self.bot_handlers: Optional[BotHandlers] = None
        self.telethon_client: Optional[TelegramClient] = None
        self.application: Optional[Application] = None
        self.web_app = None
        self.runner = None
        self.site = None
        self._shutdown_event = asyncio.Event()
        
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
            
            # Initialize web application for health checks
            self.web_app = web.Application()
            self.setup_routes()
            
            logger.info("Bot handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    def setup_routes(self):
        """Set up routes for the web server."""
        self.web_app.router.add_get('/', self.health_check)
        self.web_app.router.add_get('/health', self.health_check)
    
    async def health_check(self, request):
        """Health check endpoint for monitoring."""
        return web.json_response({
            'status': 'ok',
            'bot': 'running',
            'timestamp': asyncio.get_event_loop().time()
        })
    
    async def run_web_server(self):
        """Run the web server on port 5000."""
        try:
            # Create application runner
            self.runner = web.AppRunner(self.web_app)
            await self.runner.setup()
            
            # Determine port from environment variable or use default
            port = int(os.environ.get('PORT', 5000))
            
            # Start TCP site
            self.site = web.TCPSite(self.runner, '0.0.0.0', port)
            await self.site.start()
            
            logger.info(f"Web server started on port {port}")
            
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
            raise
    
    async def run(self):
        """Start the bot and web server."""
        try:
            await self.initialize()
            logger.info("Starting Telegram File Bot...")
            
            # Start the web server
            await self.run_web_server()
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot is running! Press Ctrl+C to stop.")
            
            # Set up signal handlers for graceful shutdown
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig, 
                    lambda: asyncio.create_task(self.shutdown())
                )
            
            # Keep the bot running until shutdown signal
            await self._shutdown_event.wait()
                
        except Exception as e:
            logger.error(f"Bot error: {e}")
            await self.shutdown()
    
    async def shutdown(self):
        """Cleanup and shutdown."""
        if self._shutdown_event.is_set():
            return
            
        logger.info("Shutting down bot...")
        self._shutdown_event.set()
        
        try:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down bot application: {e}")
        
        try:
            if self.telethon_client:
                await self.telethon_client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting telethon client: {e}")
        
        try:
            if self.runner:
                await self.runner.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up web runner: {e}")
        
        logger.info("Bot shutdown complete")

async def main():
    """Main entry point."""
    bot = TelegramFileBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
