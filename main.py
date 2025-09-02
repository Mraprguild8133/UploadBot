#!/usr/bin/env python3
"""
Telegram Bot with 4GB file handling.
Supports Telegram Bot API and Telethon (MTProto).
"""

import logging
import os
from typing import Optional, Dict, Any

from telegram.ext import Application, CommandHandler, ContextTypes
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
    """Handlers for Telegram bot commands."""

    def __init__(self, telethon_client: TelegramClient, config: Config):
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
        self.telethon_client = TelegramClient(
            "bot_session", self.config.API_ID, self.config.API_HASH
        )
        await self.telethon_client.start(bot_token=self.config.BOT_TOKEN)

        # Init Telegram Bot API client
        request = HTTPXRequest(connection_pool_size=100)
        self.application = (
            Application.builder()
            .token(self.config.BOT_TOKEN)
            .request(request)
            .build()
        )

        # Register handlers
        self.bot_handlers = BotHandlers(self.telethon_client, self.config)
        self.application.add_handler(CommandHandler("start", self.bot_handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.bot_handlers.help_command))

    def run(self):
        # Run inside Application's own loop (no asyncio.run)
        self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramFileBot()
    import asyncio
    asyncio.get_event_loop().run_until_complete(bot.initialize())
    bot.run()
    
