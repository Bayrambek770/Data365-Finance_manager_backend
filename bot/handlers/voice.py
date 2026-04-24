import logging
import os
import tempfile
from telegram import Update
from telegram.ext import ContextTypes

from bot.utils.groq_client import GroqClient
from bot.handlers.text import handle_text

logger = logging.getLogger(__name__)
groq = GroqClient()


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    processing_msg = await update.message.reply_text("🎙 Processing your voice message...")

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name

        await file.download_to_drive(tmp_path)

        try:
            transcription = groq.transcribe_voice(tmp_path)
        finally:
            os.unlink(tmp_path)

        await processing_msg.edit_text(
            f"📝 I heard: '{transcription}'\nAnalyzing..."
        )

        await handle_text(update, context, transcribed_text=transcription)

    except Exception as exc:
        logger.error("Voice processing error: %s", exc)
        await processing_msg.edit_text(
            "Sorry, I couldn't process your voice message. Please try again or type your message."
        )
