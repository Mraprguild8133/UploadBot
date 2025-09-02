#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling, compression, and Mega.nz storage integration.
Supports both Bot API and MTProto for large file transfers.
Includes Render.com deployment support with port 5000.
"""

import asyncio
import logging
import os
import sys
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
            
            logger.info("Bot handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def run_webhook(self):
        """Run the bot with webhook for Render deployment."""
        try:
            await self.initialize()
            logger.info("Starting Telegram File Bot with webhook for Render...")
            
            # Get the port from environment variable (Render provides this)
            port = int(os.environ.get('PORT', 5000))
            webhook_url = os.environ.get('WEBHOOK_URL', '')
            
            if not webhook_url:
                logger.error("WEBHOOK_URL environment variable is required for webhook mode")
                sys.exit(1)
                
            # Set up webhook
            await self.application.bot.set_webhook(
                url=f"{webhook_url}/{self.config.BOT_TOKEN}",
                drop_pending_updates=True
            )
            
            # Start the webhook server
            await self.application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=webhook_url,
                secret_token='WEBHOOK_SECRET'  # Optional security measure
            )
            
            logger.info(f"Bot is running with webhook on port {port}!")
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.shutdown()
    
    async def run_polling(self):
        """Run the bot with polling (for local development)."""
        try:
            await self.initialize()
            logger.info("Starting Telegram File Bot with polling...")
            
            # Start the bot with polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot is running with polling! Press Ctrl+C to stop.")
            
            # Keep the bot running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.shutdown()
    
    async def run(self):
        """Start the bot in the appropriate mode based on environment."""
        # Check if we're running on Render (has PORT environment variable)
        if os.environ.get('PORT'):
            await self.run_webhook()
        else:
            await self.run_polling()
    
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
