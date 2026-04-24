import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from bot.utils import api_client

logger = logging.getLogger(__name__)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Add Category"), KeyboardButton("📋 My Transactions")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    telegram_id = user.id

    try:
        # Check registration status (register with placeholder phone if new)
        result = await api_client.register_user(
            telegram_id=telegram_id,
            phone_number=f"tg_{telegram_id}",  # placeholder until real phone shared
            full_name=user.full_name or "",
            username=user.username or "",
            language="en",
        )
        is_new_user = result.get("is_new_user", False)
        is_registered = result.get("is_registered", False)

        # Store user info in context
        context.user_data["telegram_id"] = telegram_id
        context.user_data["unique_code"] = result.get("unique_code")
        context.user_data["dashboard_url"] = result.get("dashboard_url")

        if is_registered:
            dashboard_url = result.get("dashboard_url", "")
            await update.message.reply_text(
                "👋 Welcome back!\n\n"
                "You can log transactions by sending me a message or voice note.\n\n"
                "Examples:\n"
                "• 'Received 500,000 UZS from client'\n"
                "• 'Spent 200,000 on logistics'\n"
                f"• 'How much did we earn this week?'\n\n"
                f'📊 <a href="{dashboard_url}">Open your dashboard</a>',
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
        else:
            # New user: ask language first
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
                    InlineKeyboardButton("🇷🇺 Russian", callback_data="lang_ru"),
                    InlineKeyboardButton("🇺🇿 Uzbek", callback_data="lang_uz"),
                ]
            ])
            await update.message.reply_text(
                "Welcome to Xisob! 🎉\n\nPlease choose your language:",
                reply_markup=keyboard,
            )

    except Exception as exc:
        logger.error("Error in handle_start: %s", exc)
        await update.message.reply_text(
            "Sorry, something went wrong. Please try /start again."
        )


async def send_phone_request(update: Update, language: str = "en") -> None:
    messages = {
        "en": "Please share your phone number to complete registration:",
        "ru": "Пожалуйста, поделитесь номером телефона для завершения регистрации:",
        "uz": "Ro'yxatdan o'tishni yakunlash uchun telefon raqamingizni ulashing:",
    }
    button_labels = {
        "en": "📱 Share Contact",
        "ru": "📱 Поделиться контактом",
        "uz": "📱 Kontakt ulashish",
    }

    msg = messages.get(language, messages["en"])
    btn = button_labels.get(language, button_labels["en"])

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(btn, request_contact=True)]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    await update.effective_message.reply_text(msg, reply_markup=keyboard)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact = update.message.contact
    tg_user = update.effective_user

    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    language = context.user_data.get("language", "en")

    try:
        result = await api_client.register_user(
            telegram_id=tg_user.id,
            phone_number=phone,
            full_name=tg_user.full_name or "",
            username=tg_user.username or "",
            language=language,
        )
    except Exception as exc:
        logger.error("Error in handle_contact (register_user): %s", exc)
        await update.message.reply_text(
            "Sorry, registration failed. Please try /start again.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    dashboard_url = result.get("dashboard_url", "")
    context.user_data["unique_code"] = result.get("unique_code")
    context.user_data["dashboard_url"] = dashboard_url

    success_messages = {
        "en": (
            "✅ Registration complete!\n\n"
            "You can now log transactions by sending me a message or voice note.\n\n"
            "Examples:\n"
            "• 'Received 500,000 UZS from client'\n"
            "• 'Spent 200,000 on logistics'\n"
            "• 'How much did we earn this week?'"
        ),
        "ru": (
            "✅ Регистрация завершена!\n\n"
            "Теперь вы можете добавлять транзакции, отправляя сообщения или голосовые заметки."
        ),
        "uz": (
            "✅ Ro'yxatdan o'tish yakunlandi!\n\n"
            "Endi xabar yoki ovozli eslatma yuborish orqali tranzaksiyalarni qo'shishingiz mumkin."
        ),
    }

    unique_code = result.get("unique_code", "")

    msg = success_messages.get(language, success_messages["en"])
    await update.message.reply_text(
        msg + f"\n\n🔑 Your secure code: <code>{unique_code}</code>",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )
    await update.message.reply_text(
        f'📊 <a href="{dashboard_url}">Open your dashboard</a>',
        parse_mode="HTML",
    )


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("pending_transaction", None)
    context.user_data.pop("missing_fields", None)
    context.user_data.pop("state", None)
    await update.message.reply_text("❌ Cancelled.")
