import logging
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ai.client import parse_transaction
from db import repository
from utils.formatters import format_amount, truncate

logger = logging.getLogger(__name__)


def _build_account_keyboard(
    accounts: list,
    callback_prefix: str,
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            f"{acc['name']} ({acc['currency']})",
            callback_data=f"{callback_prefix}:{acc['id']}",
        )]
        for acc in accounts
    ]
    buttons.append([InlineKeyboardButton("Cancel", callback_data=f"{callback_prefix}:cancel")])
    return InlineKeyboardMarkup(buttons)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    user = await repository.get_user(user_id)
    if not user:
        await repository.upsert_user(
            user_id=user_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
        )
        user = await repository.get_user(user_id)

    accounts = await repository.get_accounts(user_id)
    if not accounts:
        await update.message.reply_text(
            "You have no accounts yet. Create one first:\n"
            "/newaccount <name> <type> <currency> [balance]\n\n"
            "Example: /newaccount Cash cash UAH 10000"
        )
        return

    thinking_msg = await update.message.reply_text("Processing...")

    try:
        parsed = await parse_transaction(
            text=text,
            user_currency=user["default_currency"],
            today=date.today(),
            account_names=[acc["name"] for acc in accounts],
        )
    except Exception as exc:
        logger.error("parse_transaction failed: %s", exc)
        await thinking_msg.edit_text("AI service is temporarily unavailable. Please try again.")
        return

    if parsed is None:
        await thinking_msg.edit_text(
            "I could not identify a transaction in that message.\n"
            "Try: 'spent 500 on food from Cash' or 'received 1200 salary to MyCard'\n"
            "Or use /help to see available commands."
        )
        return

    resolved_account = None
    if parsed.account_name:
        resolved_account = await repository.get_account_by_name(user_id, parsed.account_name)

    if resolved_account and parsed.confidence >= 0.6:
        await thinking_msg.delete()
        await _save_and_confirm(
            update=update,
            context=context,
            user_id=user_id,
            parsed=parsed,
            account=resolved_account,
            raw=text,
        )
        return

    context.user_data["pending_tx"] = {"parsed": parsed, "raw": text}

    if len(accounts) == 1 and parsed.confidence >= 0.6:
        await thinking_msg.delete()
        await _save_and_confirm(
            update=update,
            context=context,
            user_id=user_id,
            parsed=parsed,
            account=accounts[0],
            raw=text,
        )
        return

    preview = (
        f"Detected transaction:\n\n"
        f"Type: {parsed.transaction_type.capitalize()}\n"
        f"Amount: {format_amount(parsed.amount, user['default_currency'])}\n"
        f"Category: {parsed.category.capitalize()}\n"
        f"Description: {truncate(parsed.description)}\n"
        f"Date: {parsed.transaction_date}\n\n"
        "Which account?"
    )
    keyboard = _build_account_keyboard(accounts, "txacc")
    await thinking_msg.edit_text(preview, reply_markup=keyboard)


async def _save_and_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    parsed,
    account: dict,
    raw: str,
) -> None:
    tx_id = await repository.add_transaction(
        user_id=user_id,
        account_id=account["id"],
        amount=parsed.amount,
        category=parsed.category,
        description=parsed.description,
        transaction_type=parsed.transaction_type,
        transaction_date=parsed.transaction_date,
        raw_input=raw,
    )

    refreshed = await repository.get_account(user_id, account["id"])
    symbol = "+" if parsed.transaction_type == "income" else "-"
    text = (
        f"Saved! #{tx_id}\n"
        f"{symbol}{format_amount(parsed.amount, account['currency'])} "
        f"[{parsed.category.capitalize()}] {truncate(parsed.description, 40)}\n"
        f"Account: {account['name']}  |  "
        f"New balance: {format_amount(refreshed['balance'], account['currency'])}"
    )

    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def callback_pick_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")[1]

    if data == "cancel":
        context.user_data.pop("pending_tx", None)
        await query.edit_message_text("Transaction cancelled.")
        return

    pending = context.user_data.pop("pending_tx", None)
    if not pending:
        await query.edit_message_text("Session expired. Please try again.")
        return

    user_id = query.from_user.id
    account_id = int(data)
    account = await repository.get_account(user_id, account_id)
    if not account:
        await query.edit_message_text("Account not found. Please try again.")
        return

    parsed = pending["parsed"]
    tx_id = await repository.add_transaction(
        user_id=user_id,
        account_id=account_id,
        amount=parsed.amount,
        category=parsed.category,
        description=parsed.description,
        transaction_type=parsed.transaction_type,
        transaction_date=parsed.transaction_date,
        raw_input=pending["raw"],
    )

    refreshed = await repository.get_account(user_id, account_id)
    symbol = "+" if parsed.transaction_type == "income" else "-"
    await query.edit_message_text(
        f"Saved! #{tx_id}\n"
        f"{symbol}{format_amount(parsed.amount, account['currency'])} "
        f"[{parsed.category.capitalize()}] {truncate(parsed.description, 40)}\n"
        f"Account: {account['name']}  |  "
        f"New balance: {format_amount(refreshed['balance'], account['currency'])}"
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    from utils.formatters import last_n_days
    start, end = last_n_days(30)
    transactions = await repository.get_transactions(
        user_id=user_id, start_date=start, end_date=end, limit=15
    )

    if not transactions:
        await update.message.reply_text("No transactions in the last 30 days.")
        return

    lines = ["Last 30 days (up to 15):\n"]
    for tx in transactions:
        symbol = "+" if tx["transaction_type"] == "income" else "-"
        acc_label = tx["account_name"] or "?"
        currency = tx["account_currency"] or user["default_currency"]
        lines.append(
            f"#{tx['id']} {tx['transaction_date'].strftime('%d %b')} "
            f"{symbol}{format_amount(tx['amount'], currency)} "
            f"[{tx['category'].capitalize()}] {acc_label} — "
            f"{truncate(tx['description'] or '', 28)}"
        )

    await update.message.reply_text("\n".join(lines))


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /delete <transaction_id>")
        return

    try:
        tx_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Transaction ID must be a number.")
        return

    user_id = update.effective_user.id
    deleted = await repository.delete_transaction(user_id=user_id, transaction_id=tx_id)

    if deleted:
        await update.message.reply_text(
            f"Transaction #{tx_id} deleted and account balance reversed."
        )
    else:
        await update.message.reply_text(
            f"Transaction #{tx_id} not found or does not belong to you."
        )