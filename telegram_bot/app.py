"""
FastAPI webhook server for the Telegram Video Editor Bot.
Used for cloud deployment (Fly.io) — runs 24/7 without polling.
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))

from bot import (
    start, help_command, music_command, sfx_command,
    status_command, handle_video, handle_audio, handle_text,
)
from telegram.ext import CommandHandler, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Bot token — fallback to hardcoded for deployment
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8724539958:AAFAlKsdlCChod86NFE7x4I50gkjucafhZM")

# Auto-detect webhook URL from FLY_APP_NAME
FLY_APP = os.environ.get("FLY_APP_NAME", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", f"https://{FLY_APP}.fly.dev" if FLY_APP else "")

# Build the telegram application
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("music", music_command))
telegram_app.add_handler(CommandHandler("sfx", sfx_command))
telegram_app.add_handler(CommandHandler("status", status_command))
telegram_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
telegram_app.add_handler(MessageHandler(
    filters.AUDIO | filters.VOICE | filters.Document.AUDIO, handle_audio))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the telegram bot."""
    # Set webhook on startup
    if WEBHOOK_URL:
        await telegram_app.initialize()
        await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        await telegram_app.start()
        logger.info(f"Webhook set: {WEBHOOK_URL}/webhook")
    else:
        # Fallback to polling if no webhook URL
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        logger.info("Started in polling mode (no WEBHOOK_URL set)")

    yield

    # Cleanup
    if WEBHOOK_URL:
        await telegram_app.bot.delete_webhook()
    else:
        await telegram_app.updater.stop()
    await telegram_app.stop()
    await telegram_app.shutdown()


app = FastAPI(title="Video Editor Bot", lifespan=lifespan)


@app.get("/")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "bot": "Video Editor Bot"}


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    """Handle incoming Telegram webhook updates."""
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return Response(status_code=200)
