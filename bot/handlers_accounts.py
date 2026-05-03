from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import repository
from utils.constants import ACCOUNT_TYPES, SUPPORTED_CURRENCIES
from utils.formatters import format_amount


async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    accounts = await repository.get_accounts(user_id)
    if not accounts:
        await update.message.reply_text(
            "You have no accounts yet.\n\n"
            "Create one with:\n"
            "/newaccount <name> <type> <currency> [initial_balance]\n\n"
            f"Types: {', '.join(ACCOUNT_TYPES)}\n"
            f"Example: /newaccount MyCard card UAH 2000"
        )
        return

    lines = ["Your accounts:\n"]
    for acc in accounts:
        sign = "+" if acc["balance"] >= 0 else ""
        lines.append(
            f"[#{acc['id']}] {acc['name']}  ({acc['account_type']})\n"
            f"  Balance: {sign}{format_amount(acc['balance'], acc['currency'])}"
        )

    lines.append(
        "\n/newaccount — add account\n"
        "/deleteaccount <id> — remove account"
    )
    await update.message.reply_text("\n".join(lines))


async def cmd_new_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or len(args) < 3:
        await update.message.reply_text(
            "Usage: /newaccount <name> <type> <currency> [initial_balance]\n\n"
            f"Types: {', '.join(ACCOUNT_TYPES)}\n"
            f"Currencies: {', '.join(sorted(SUPPORTED_CURRENCIES))}\n\n"
            "Examples:\n"
            "  /newaccount Cash cash UAH 10000\n"
            "  /newaccount MyCard card USD 500\n"
            "  /newaccount Savings savings EUR 1000"
        )
        return

    name = args[0]
    account_type = args[1].lower()
    currency = args[2].upper()
    initial_balance = Decimal("0")

    if len(name) > 32:
        await update.message.reply_text("Account name must be 32 characters or less.")
        return

    if account_type not in ACCOUNT_TYPES:
        await update.message.reply_text(
            f"Unknown type '{account_type}'.\nValid types: {', '.join(ACCOUNT_TYPES)}"
        )
        return

    if currency not in SUPPORTED_CURRENCIES:
        await update.message.reply_text(
            f"Unsupported currency '{currency}'.\n"
            f"Supported: {', '.join(sorted(SUPPORTED_CURRENCIES))}"
        )
        return

    if len(args) >= 4:
        try:
            initial_balance = Decimal(args[3].replace(",", "."))
        except InvalidOperation:
            await update.message.reply_text("Initial balance must be a number.")
            return

    user_id = update.effective_user.id
    account = await repository.create_account(
        user_id=user_id,
        name=name,
        account_type=account_type,
        currency=currency,
        initial_balance=initial_balance,
    )

    if account is None:
        await update.message.reply_text(
            f"An account named '{name}' already exists. Choose a different name."
        )
        return

    await update.message.reply_text(
        f"Account created!\n\n"
        f"Name: {account['name']}\n"
        f"Type: {account['account_type']}\n"
        f"Currency: {account['currency']}\n"
        f"Balance: {format_amount(account['balance'], account['currency'])}\n\n"
        f"Now you can log transactions to it:\n"
        f"'spent 500 on food from {account['name']}' or\n"
        f"'received 1000 salary to {account['name']}'"
    )


async def cmd_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /deleteaccount <account_id>\nSee /accounts for IDs.")
        return

    try:
        account_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Account ID must be a number.")
        return

    user_id = update.effective_user.id
    account = await repository.get_account(user_id, account_id)
    if not account:
        await update.message.reply_text(f"Account #{account_id} not found.")
        return

    context.user_data["delete_account_id"] = account_id
    context.user_data["delete_account_name"] = account["name"]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, delete", callback_data=f"delacc:{account_id}"),
            InlineKeyboardButton("Cancel", callback_data="delacc:cancel"),
        ]
    ])
    await update.message.reply_text(
        f"Delete account '{account['name']}' (balance: {format_amount(account['balance'], account['currency'])})?\n"
        "All transaction history for this account will be kept but unlinked.",
        reply_markup=keyboard,
    )


async def callback_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")[1]

    if data == "cancel":
        context.user_data.pop("delete_account_id", None)
        context.user_data.pop("delete_account_name", None)
        await query.edit_message_text("Cancelled.")
        return

    user_id = query.from_user.id
    account_id = int(data)
    name = context.user_data.pop("delete_account_name", f"#{account_id}")
    context.user_data.pop("delete_account_id", None)

    deleted = await repository.delete_account(user_id, account_id)
    if deleted:
        await query.edit_message_text(f"Account '{name}' deleted.")
    else:
        await query.edit_message_text("Account not found or already deleted.")