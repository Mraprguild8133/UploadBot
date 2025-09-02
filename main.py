#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling, compression, and Mega.nz storage integration.
Supports both Bot API and MTProto for large file transfers.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any
from pathlib import Path

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
from telegram.request import HTTPXRequest
from telethon import TelegramClient
from mega import Mega

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class Config:
    """Configuration class for the bot."""

    def __init__(self):
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.API_ID = int(os.getenv("API_ID", 0))
        self.API_HASH = os.getenv("API_HASH")
        self.MEGA_EMAIL = os.getenv("MEGA_EMAIL")
        self.MEGA_PASSWORD = os.getenv("MEGA_PASSWORD")
        self.MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB

        if not all([self.BOT_TOKEN, self.API_ID, self.API_HASH]):
            raise ValueError("Missing required environment variables: BOT_TOKEN, API_ID, API_HASH")


class MegaStorage:
    """Handler for Mega.nz storage operations."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.mega = Mega()
        self.logged_in = False

    async def login(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.mega.login, self.email, self.password)
        self.logged_in = True
        logger.info("Logged in to Mega.nz")

    async def upload_file(self, file_path: str, file_name: Optional[str] = None) -> Optional[str]:
        if not self.logged_in:
            await self.login()
        loop = asyncio.get_running_loop()
        if not file_name:
            file_name = os.path.basename(file_path)
        file = await loop.run_in_executor(None, self.mega.upload, file_path, None, file_name)
        download_url = await loop.run_in_executor(None, self.mega.get_upload_link, file)
        return download_url

    async def download_file(self, url: str, download_path: Optional[str] = None) -> Optional[str]:
        if not self.logged_in:
            await self.login()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.mega.download_url, url, download_path)


class BotHandlers:
    """Handlers for Telegram bot commands and messages."""

    def __init__(self, bot_app: Application, telethon_client: TelegramClient, config: Config, mega_storage: Optional[MegaStorage]):
        self.bot_app = bot_app
        self.telethon_client = telethon_client
        self.config = config
        self.mega_storage = mega_storage
        self.user_sessions: Dict[int, Dict[str, Any]] = {}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_text(
            f"Hi {user.mention_html()} 👋\n\n"
            "I'm a file handling bot with support for large files up to 4GB.\n"
            "I can help you store, compress, and manage your files with Mega.nz integration.\n\n"
            "Use /help to see all available commands.",
            parse_mode="HTML",
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📚 <b>Available Commands:</b>\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/upload - Upload a file to Mega.nz\n"
            "/download <url> - Download from Mega.nz\n"
            "/list - List your files\n"
            "/delete - Delete a file\n"
            "/compress - Compress files\n"
            "/settings - Preferences\n\n"
            "Or just send me a file!"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")


class TelegramFileBot:
    def __init__(self):
        self.config = Config()
        self.application: Optional[Application] = None
        self.telethon_client: Optional[TelegramClient] = None
        self.mega_storage: Optional[MegaStorage] = None
        self.bot_handlers: Optional[BotHandlers] = None

    async def initialize(self):
        if self.config.MEGA_EMAIL and self.config.MEGA_PASSWORD:
            self.mega_storage = MegaStorage(self.config.MEGA_EMAIL, self.config.MEGA_PASSWORD)
            await self.mega_storage.login()
        else:
            self.mega_storage = None

        self.telethon_client = TelegramClient("bot_session", self.config.API_ID, self.config.API_HASH)
        await self.telethon_client.start(bot_token=self.config.BOT_TOKEN)

        request = HTTPXRequest(connection_pool_size=100, read_timeout=30, write_timeout=30, connect_timeout=30)
        self.application = Application.builder().token(self.config.BOT_TOKEN).request(request).build()

        self.bot_handlers = BotHandlers(self.application, self.telethon_client, self.config, self.mega_storage)

        self.application.add_handler(CommandHandler("start", self.bot_handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.bot_handlers.help_command))

    async def run(self):
        await self.initialize()
        logger.info("Running bot in polling mode")
        await self.application.run_polling()


async def main():
    bot = TelegramFileBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
        
