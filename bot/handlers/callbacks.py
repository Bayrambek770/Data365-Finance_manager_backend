import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils import api_client
from bot.utils.formatter import fmt_amount, fmt_budget_warning, fmt_transaction
from bot.handlers.start import send_phone_request

logger = logging.getLogger(__name__)

FIELD_PROMPTS = {
    "amount": "💰 Enter new amount:",
    "category": "Enter new category name:",
    "note": "Enter new note (or 'skip' to remove):",
    "date": "Enter new date (YYYY-MM-DD):",
    "currency": "Enter currency (UZS or USD):",
    "type": "Enter type (income or expense):",
}


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    # Language selection
    if data.startswith("lang_"):
        await _handle_language(update, context, data)

    elif data == "confirm_transaction":
        await _confirm_transaction(query, context)

    elif data == "cancel_transaction":
        await _cancel_transaction(query, context)

    elif data == "edit_transaction":
        await _show_edit_menu(query, context)

    elif data.startswith("edit_field_"):
        field = data.replace("edit_field_", "")
        await _ask_edit_field(query, context, field)

    elif data.startswith("newcat_"):
        await _handle_newcat_type(query, context, data)

    elif data == "delete_confirm":
        await _delete_transaction(query, context)

    elif data == "delete_cancel":
        context.user_data.pop("deleting_transaction", None)
        await query.edit_message_text("❌ Deletion cancelled.")


# ── Language ─────────────────────────────────────────────────────────────────

async def _handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    query = update.callback_query
    lang_map = {"lang_en": "en", "lang_ru": "ru", "lang_uz": "uz"}
    language = lang_map.get(data, "en")
    context.user_data["language"] = language

    lang_labels = {"en": "English", "ru": "Russian", "uz": "Uzbek"}
    await query.edit_message_text(
        f"✅ Language set to {lang_labels[language]}!"
    )
    await send_phone_request(update, language)


# ── Confirm Transaction ───────────────────────────────────────────────────────

async def _confirm_transaction(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = context.user_data.get("pending_transaction")
    if not pending:
        await query.edit_message_text("No pending transaction found.")
        return

    telegram_id = context.user_data.get("telegram_id") or query.from_user.id

    try:
        result = await api_client.create_transaction(
            telegram_id=telegram_id,
            amount=pending.get("amount", 0),
            currency=pending.get("currency", "UZS"),
            tx_type=pending.get("type", "expense"),
            category_id=pending.get("category_id", ""),
            tx_date=pending.get("date") or date.today().isoformat(),
            note=pending.get("note") or "",
        )

        amount = pending.get("amount", 0)
        currency = pending.get("currency", "UZS")
        category = pending.get("category_name", "")
        tx_type = pending.get("type", "")
        emoji = "💰" if tx_type == "income" else "💸"

        success_msg = f"✅ {emoji} Transaction saved!\n{fmt_amount(amount, currency)} — {category}"

        budget_warning = result.get("budget_warning")
        if budget_warning:
            warning_text = fmt_budget_warning(budget_warning)
            success_msg += f"\n\n{warning_text}"

        await query.edit_message_text(success_msg)

    except Exception as exc:
        logger.error("Failed to save transaction: %s", exc)
        await query.edit_message_text(
            "❌ Failed to save transaction. Please try again."
        )
    finally:
        context.user_data.pop("pending_transaction", None)
        context.user_data.pop("missing_fields", None)
        context.user_data.pop("state", None)


# ── Cancel ────────────────────────────────────────────────────────────────────

async def _cancel_transaction(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("pending_transaction", None)
    context.user_data.pop("missing_fields", None)
    context.user_data.pop("state", None)
    context.user_data.pop("editing_transaction", None)
    await query.edit_message_text("❌ Cancelled.")


# ── Edit ──────────────────────────────────────────────────────────────────────

async def _show_edit_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Amount", callback_data="edit_field_amount"),
            InlineKeyboardButton("Category", callback_data="edit_field_category"),
            InlineKeyboardButton("Currency", callback_data="edit_field_currency"),
        ],
        [
            InlineKeyboardButton("Type", callback_data="edit_field_type"),
            InlineKeyboardButton("Date", callback_data="edit_field_date"),
            InlineKeyboardButton("Note", callback_data="edit_field_note"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_transaction")],
    ])
    await query.edit_message_text("What would you like to edit?", reply_markup=keyboard)


async def _ask_edit_field(query, context: ContextTypes.DEFAULT_TYPE, field: str) -> None:
    context.user_data["state"] = "editing_field"
    context.user_data["editing_field"] = field
    prompt = FIELD_PROMPTS.get(field, f"Enter new {field}:")
    await query.edit_message_text(prompt)


# ── New Category ─────────────────────────────────────────────────────────────

async def _handle_newcat_type(query, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    cat_type = data.replace("newcat_", "")   # "income" or "expense"
    context.user_data["new_category_type"] = cat_type
    context.user_data["state"] = "adding_category"
    emoji = "💰" if cat_type == "income" else "💸"
    await query.edit_message_text(f"{emoji} Enter the category name:")


# ── Delete ────────────────────────────────────────────────────────────────────

async def _delete_transaction(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    tx = context.user_data.get("deleting_transaction")
    if not tx:
        await query.edit_message_text("No transaction to delete.")
        return

    telegram_id = context.user_data.get("telegram_id") or query.from_user.id

    try:
        await api_client.delete_transaction(telegram_id, tx["id"])
        await query.edit_message_text("✅ Transaction deleted.")
    except Exception as exc:
        logger.error("Delete failed: %s", exc)
        await query.edit_message_text("❌ Failed to delete transaction.")
    finally:
        context.user_data.pop("deleting_transaction", None)
