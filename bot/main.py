import logging
import os
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from bot.handlers.start import handle_start, handle_contact, handle_cancel
from bot.handlers.voice import handle_voice
from bot.handlers.text import handle_text
from bot.handlers.callbacks import handle_callback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(token).build()

    # Command handlers
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("cancel", handle_cancel))

    # Contact (phone number sharing)
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # Voice messages
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
