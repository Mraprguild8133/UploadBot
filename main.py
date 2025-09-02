#!/usr/bin/env python3
"""
Telegram Bot supporting only port 5000 for webhook.
Supports large file handling, compression, and Mega.nz storage.
"""

import os
import asyncio
import logging
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

# Telegram bot token
TOKEN = os.getenv('BOT_TOKEN')

# Webhook URL (must include port 5000)
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'https://yourdomain.com')  # Replace with your domain
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}:{5000}{WEBHOOK_PATH}"

# Instantiate Telethon client (for large file handling)
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

# Initialize bot application
application = None
telethon_client = None

async def start_webhook(request):
    """Handle incoming webhook updates from Telegram."""
    update = await request.json()
    # Pass to the application for processing
    update_obj = telegram.Update.de_json(update, application.bot)
    await application.process_update(update_obj)
    return web.Response()

async def init_app():
    global application, telethon_client

    # Initialize Telethon client
    telethon_client = TelegramClient('bot_session', API_ID, API_HASH)
    await telethon_client.start(bot_token=TOKEN)
    logger.info("Telethon client started.")

    # Initialize Telegram Application
    application = Application.builder().token(TOKEN).build()

    # Register command handlers
    from bot.handlers import BotHandlers
    bot_handlers = BotHandlers(application, telethon_client, Config())

    application.add_handler(CommandHandler("start", bot_handlers.start_command))
    application.add_handler(CommandHandler("help", bot_handlers.help_command))
    application.add_handler(CommandHandler("upload", bot_handlers.upload_command))
    application.add_handler(CommandHandler("download", bot_handlers.download_command))
    application.add_handler(CommandHandler("list", bot_handlers.list_files_command))
    application.add_handler(CommandHandler("delete", bot_handlers.delete_file_command))
    application.add_handler(CommandHandler("compress", bot_handlers.compress_command))
    application.add_handler(CommandHandler("settings", bot_handlers.settings_command))
    # File upload handler
    file_filter = filters.Document | filters.Photo | filters.Video | filters.Audio
    application.add_handler(MessageHandler(file_filter, bot_handlers.handle_file_upload))

    # Set webhook
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    # Set up aiohttp web server
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, start_webhook)
    return app

async def main():
    app = await init_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 5000)
    await site.start()
    logger.info("Webhook server listening on port 5000")
    try:
        # Keep running until interrupted
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Cleanup
        await application.bot.delete_webhook()
        await telethon_client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
