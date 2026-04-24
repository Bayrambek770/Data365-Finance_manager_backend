import logging
from datetime import date
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils import api_client
from bot.utils.intent_parser import parse_user_message
from bot.utils.formatter import (
    fmt_transaction_confirmation,
    fmt_transaction,
    help_text,
    fmt_amount,
)
from bot.handlers.categories import handle_add_category, handle_category_name
from bot.handlers.transactions_list import handle_transactions_list

logger = logging.getLogger(__name__)

FIELD_PROMPTS = {
    "amount": "💰 Please enter the amount (e.g. 500000):",
    "currency": "What currency? Reply UZS or USD:",
    "type": "Is this an income or expense? Reply 'income' or 'expense':",
    "category": "What category? (e.g. Sales, Salaries, Logistics):",
    "date": "What date? (YYYY-MM-DD or 'today'):",
    "note": "Any note? (or reply 'skip' to leave blank):",
}


async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    transcribed_text: Optional[str] = None,
) -> None:
    text = transcribed_text or update.message.text or ""
    telegram_id = update.effective_user.id

    # ── Persistent menu buttons ──────────────────────────────────────────────
    if text == "➕ Add Category":
        await handle_add_category(update, context)
        return
    if text == "📋 My Transactions":
        await handle_transactions_list(update, context)
        return

    # ── Handle pending state: user is answering a missing-field prompt ──────
    state = context.user_data.get("state")

    if state == "asking_field":
        await _handle_field_reply(update, context, text, telegram_id)
        return

    if state == "adding_category":
        await handle_category_name(update, context)
        return

    if state == "editing_field":
        await _handle_edit_field_reply(update, context, text, telegram_id)
        return

    if state == "confirming":
        await update.message.reply_text(
            "Please use the buttons above to Confirm, Cancel, or Edit the transaction."
        )
        return

    # ── Fresh intent parsing ─────────────────────────────────────────────────
    parsed = await parse_user_message(telegram_id, text)
    intent = parsed.get("intent", "unknown")

    if intent == "log_transaction":
        await _handle_log_transaction(update, context, parsed, telegram_id)

    elif intent == "query":
        await _handle_query(update, context, text, telegram_id)

    elif intent == "edit_last":
        await _handle_edit_last(update, context, telegram_id)

    elif intent == "delete_last":
        await _handle_delete_last(update, context, telegram_id)

    else:
        await update.message.reply_text(help_text())


# ── Intent Handlers ──────────────────────────────────────────────────────────

async def _handle_log_transaction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parsed: dict,
    telegram_id: int,
) -> None:
    pending = {
        "amount": parsed.get("amount"),
        "currency": parsed.get("currency") or "UZS",
        "type": parsed.get("type"),
        "category_id": parsed.get("category_id"),
        "category_name": parsed.get("category_name") or parsed.get("category"),
        "date": parsed.get("date") or date.today().isoformat(),
        "note": parsed.get("note"),
    }
    context.user_data["pending_transaction"] = pending

    missing = list(parsed.get("missing_fields", []))
    # Also catch fields that are still None
    for field in ("amount", "type", "category_id"):
        if pending.get(field) is None and field not in missing:
            key = "category" if field == "category_id" else field
            missing.append(key)

    context.user_data["missing_fields"] = missing

    if missing:
        first = missing[0]
        context.user_data["state"] = "asking_field"
        context.user_data["current_asking"] = first
        await update.message.reply_text(FIELD_PROMPTS.get(first, f"Please provide {first}:"))
    else:
        await _show_confirmation(update, context, pending)


async def _handle_field_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    telegram_id: int,
) -> None:
    pending = context.user_data.get("pending_transaction", {})
    missing = context.user_data.get("missing_fields", [])
    current = context.user_data.get("current_asking", "")

    # Parse the user's answer
    if current == "amount":
        try:
            amount = float(text.replace(",", "").replace(" ", ""))
            pending["amount"] = amount
            missing = [f for f in missing if f != "amount"]
        except ValueError:
            await update.message.reply_text("Please enter a valid number (e.g. 500000):")
            return

    elif current == "currency":
        val = text.strip().upper()
        if val in ("UZS", "USD"):
            pending["currency"] = val
            missing = [f for f in missing if f != "currency"]
        else:
            await update.message.reply_text("Please reply with UZS or USD:")
            return

    elif current == "type":
        val = text.strip().lower()
        if val in ("income", "expense"):
            pending["type"] = val
            missing = [f for f in missing if f != "type"]
        else:
            await update.message.reply_text("Please reply with 'income' or 'expense':")
            return

    elif current == "category":
        categories = await api_client.get_categories(telegram_id)
        cat_lower = text.strip().lower()
        match = None
        for c in categories:
            if c["name"].lower() == cat_lower:
                match = c
                break
        if match is None:
            for c in categories:
                if cat_lower in c["name"].lower():
                    match = c
                    break
        if match:
            pending["category_id"] = match["id"]
            pending["category_name"] = match["name"]
            if pending.get("type") is None:
                pending["type"] = match["type"]
            missing = [f for f in missing if f not in ("category", "category_id")]
        else:
            cat_names = ", ".join(c["name"] for c in categories)
            await update.message.reply_text(
                f"Category not found. Available: {cat_names}\n\nPlease try again:"
            )
            return

    elif current == "date":
        val = text.strip().lower()
        if val in ("today", "сегодня", "bugun"):
            pending["date"] = date.today().isoformat()
        else:
            try:
                from datetime import datetime
                datetime.strptime(val, "%Y-%m-%d")
                pending["date"] = val
            except ValueError:
                await update.message.reply_text("Please enter date as YYYY-MM-DD or 'today':")
                return
        missing = [f for f in missing if f != "date"]

    elif current == "note":
        if text.strip().lower() not in ("skip", "none", "-"):
            pending["note"] = text.strip()
        missing = [f for f in missing if f != "note"]

    context.user_data["pending_transaction"] = pending
    context.user_data["missing_fields"] = missing

    if missing:
        next_field = missing[0]
        context.user_data["current_asking"] = next_field
        await update.message.reply_text(FIELD_PROMPTS.get(next_field, f"Please provide {next_field}:"))
    else:
        context.user_data["state"] = "confirming"
        await _show_confirmation(update, context, pending)


async def _show_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pending: dict,
) -> None:
    context.user_data["state"] = "confirming"
    text = fmt_transaction_confirmation(pending)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="confirm_transaction"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_transaction"),
            InlineKeyboardButton("✏️ Edit", callback_data="edit_transaction"),
        ]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)


async def _handle_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question: str,
    telegram_id: int,
) -> None:
    try:
        result = await api_client.query_natural_language(telegram_id, question)
        await update.message.reply_text(result.get("answer", "No answer available."))
    except Exception as exc:
        logger.error("Query error: %s", exc)
        await update.message.reply_text("Sorry, I couldn't process that query. Please try again.")


async def _handle_edit_last(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
) -> None:
    try:
        tx = await api_client.get_last_transaction(telegram_id)
        context.user_data["editing_transaction"] = tx
        context.user_data["state"] = "editing"
        tx_text = fmt_transaction(tx)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Amount", callback_data="edit_field_amount"),
                InlineKeyboardButton("Category", callback_data="edit_field_category"),
                InlineKeyboardButton("Note", callback_data="edit_field_note"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_transaction")],
        ])
        await update.message.reply_text(
            f"Last transaction:\n{tx_text}\n\nWhat would you like to edit?",
            reply_markup=keyboard,
        )
    except Exception:
        await update.message.reply_text("No recent transactions found.")


async def _handle_delete_last(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
) -> None:
    try:
        tx = await api_client.get_last_transaction(telegram_id)
        context.user_data["deleting_transaction"] = tx
        tx_text = fmt_transaction(tx)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, delete", callback_data="delete_confirm"),
                InlineKeyboardButton("❌ No", callback_data="delete_cancel"),
            ]
        ])
        await update.message.reply_text(
            f"Delete this transaction?\n{tx_text}",
            reply_markup=keyboard,
        )
    except Exception:
        await update.message.reply_text("No recent transactions found.")


async def _handle_edit_field_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    telegram_id: int,
) -> None:
    field = context.user_data.get("editing_field")
    saved_tx = context.user_data.get("editing_transaction")   # editing a saved tx via "edit last"
    pending = context.user_data.get("pending_transaction")     # editing the pending confirmation

    if not field or (not saved_tx and not pending):
        await update.message.reply_text("No edit in progress.")
        context.user_data.pop("state", None)
        return

    # ── Parse the typed value ────────────────────────────────────────────────
    parsed = {}

    if field == "amount":
        try:
            parsed["amount"] = float(text.replace(",", "").replace(" ", ""))
        except ValueError:
            await update.message.reply_text("Please enter a valid number (e.g. 500000):")
            return

    elif field == "currency":
        val = text.strip().upper()
        if val not in ("UZS", "USD"):
            await update.message.reply_text("Please reply with UZS or USD:")
            return
        parsed["currency"] = val

    elif field == "type":
        val = text.strip().lower()
        if val not in ("income", "expense"):
            await update.message.reply_text("Please reply with 'income' or 'expense':")
            return
        parsed["type"] = val

    elif field == "category":
        categories = await api_client.get_categories(telegram_id)
        cat_lower = text.strip().lower()
        match = None
        for c in categories:
            if c["name"].lower() == cat_lower:
                match = c
                break
        if match is None:
            for c in categories:
                if cat_lower in c["name"].lower():
                    match = c
                    break
        if match:
            parsed["category_id"] = match["id"]
            parsed["category_name"] = match["name"]
        else:
            cat_names = ", ".join(c["name"] for c in categories)
            await update.message.reply_text(
                f"Category not found. Available: {cat_names}\n\nPlease try again:"
            )
            return

    elif field == "date":
        val = text.strip().lower()
        if val in ("today", "сегодня", "bugun"):
            from datetime import date
            parsed["date"] = date.today().isoformat()
        else:
            try:
                from datetime import datetime
                datetime.strptime(val, "%Y-%m-%d")
                parsed["date"] = val
            except ValueError:
                await update.message.reply_text("Please enter date as YYYY-MM-DD or 'today':")
                return

    elif field == "note":
        parsed["note"] = text.strip() if text.strip().lower() not in ("skip", "none", "-") else ""

    context.user_data.pop("editing_field", None)
    context.user_data.pop("state", None)

    # ── Apply: pending confirmation edit → update dict and re-show confirmation
    if pending is not None:
        pending.update(parsed)
        context.user_data["pending_transaction"] = pending
        await _show_confirmation(update, context, pending)
        return

    # ── Apply: saved transaction edit → call API ─────────────────────────────
    try:
        await api_client.update_transaction(telegram_id, saved_tx["id"], parsed)
        await update.message.reply_text(f"✅ {field.capitalize()} updated successfully!")
    except Exception as exc:
        logger.error("Update transaction failed: %s", exc)
        await update.message.reply_text("❌ Failed to update. Please try again.")
    finally:
        context.user_data.pop("editing_transaction", None)
