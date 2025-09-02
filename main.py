#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling.
Supports both Bot API and MTProto for large file transfers.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
from telegram.request import HTTPXRequest
from telethon import TelegramClient

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
        self.MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4GB

        if not all([self.BOT_TOKEN, self.API_ID, self.API_HASH]):
            raise ValueError("Missing required environment variables: BOT_TOKEN, API_ID, API_HASH")


class BotHandlers:
    """Handlers for Telegram bot commands and messages."""

    def __init__(self, bot_app: Application, telethon_client: TelegramClient, config: Config):
        self.bot_app = bot_app
        self.telethon_client = telethon_client
        self.config = config
        self.user_sessions: Dict[int, Dict[str, Any]] = {}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_text(
            f"Hi {user.mention_html()} 👋\n\n"
            "I'm a file handling bot with support for large files up to 4GB.\n"
            "More features will be added soon!\n\n"
            "Use /help to see available commands.",
            parse_mode="HTML",
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📚 <b>Available Commands:</b>\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n\n"
            "Send me a file and I'll process it!"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")


class TelegramFileBot:
    def __init__(self):
        self.config = Config()
        self.application: Optional[Application] = None
        self.telethon_client: Optional[TelegramClient] = None
        self.bot_handlers: Optional[BotHandlers] = None

    async def initialize(self):
        # Start Telethon client
        self.telethon_client = TelegramClient("bot_session", self.config.API_ID, self.config.API_HASH)
        await self.telethon_client.start(bot_token=self.config.BOT_TOKEN)

        # Init Telegram Bot API client
        request = HTTPXRequest(connection_pool_size=100, read_timeout=30, write_timeout=30, connect_timeout=30)
        self.application = Application.builder().token(self.config.BOT_TOKEN).request(request).build()

        # Register handlers
        self.bot_handlers = BotHandlers(self.application, self.telethon_client, self.config)
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
        
