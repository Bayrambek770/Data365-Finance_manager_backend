import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils import api_client

logger = logging.getLogger(__name__)


async def handle_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Income", callback_data="newcat_income"),
            InlineKeyboardButton("💸 Expense", callback_data="newcat_expense"),
        ]
    ])
    await update.message.reply_text(
        "What type of category do you want to add?",
        reply_markup=keyboard,
    )


async def handle_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.message.text.strip()
    cat_type = context.user_data.get("new_category_type")
    telegram_id = update.effective_user.id

    if not cat_type:
        await update.message.reply_text("Something went wrong. Please tap '➕ Add Category' again.")
        return

    context.user_data.pop("state", None)
    context.user_data.pop("new_category_type", None)

    try:
        result = await api_client.create_category(telegram_id, name, cat_type)
        emoji = "💰" if cat_type == "income" else "💸"
        await update.message.reply_text(
            f"✅ Category added!\n{emoji} {result['name']} ({cat_type})"
        )
    except Exception as exc:
        msg = str(exc)
        if "409" in msg or "already exists" in msg.lower():
            await update.message.reply_text(f"⚠️ A category named '{name}' already exists.")
        else:
            logger.error("create_category failed: %s", exc)
            await update.message.reply_text("❌ Failed to create category. Please try again.")
