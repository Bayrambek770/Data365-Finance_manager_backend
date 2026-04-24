import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.utils import api_client

logger = logging.getLogger(__name__)


async def handle_transactions_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    try:
        txs = await api_client.list_transactions(telegram_id, limit=15)
    except Exception as exc:
        logger.error("list_transactions failed: %s", exc)
        await update.message.reply_text("❌ Could not load transactions. Please try again.")
        return

    if not txs:
        await update.message.reply_text("No transactions found yet.\n\nSend me a message to log one!")
        return

    lines = ["📋 <b>Last 15 transactions:</b>\n"]
    for tx in txs:
        emoji = "💰" if tx["type"] == "income" else "💸"
        amount = tx["amount"]
        currency = tx["currency"]
        if currency == "USD":
            amount_str = f"${amount:,.2f}"
        else:
            amount_str = f"{amount:,.0f} {currency}"
        category = tx["category_name"]
        date = tx["date"]
        note = f" — {tx['note']}" if tx.get("note") else ""
        lines.append(f"{emoji} <b>{amount_str}</b> · {category} · {date}{note}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
