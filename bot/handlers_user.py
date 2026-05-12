from decimal import Decimal, InvalidOperation

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import repository
from utils.constants import SUPPORTED_CURRENCIES
from utils.formatters import format_amount


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await repository.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )

    text = (
        f"Welcome, {user.first_name}!\n\n"
        "I am your personal finance assistant, guided by the wisdom of the Dharma.\n\n"
        "Get started by creating an account:\n"
        "/newaccount <name> <type> <currency> [balance]\n\n"
        "Examples:\n"
        "  /newaccount Cash cash UAH 10000\n"
        "  /newaccount MyCard card USD 500\n"
        "  /newaccount Savings savings EUR 1000\n\n"
        "Then just type to log transactions:\n"
        "  'spent 200 on food from Cash'\n"
        "  'received 5000 salary to MyCard'\n\n"
        "Ask the Buddha for financial wisdom: /buddha <your question>\n\n"
        "Use /help to see all commands."
    )
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Available commands:\n\n"
        "Accounts:\n"
        "  /accounts — list all accounts with balances\n"
        "  /newaccount <name> <type> <currency> [balance]\n"
        "  /deleteaccount <id> — remove an account\n\n"
        "Transactions:\n"
        "  Just type naturally: 'spent 200 on food from Cash'\n"
        "  /history — last 15 transactions\n"
        "  /delete <id> — delete and reverse a transaction\n\n"
        "Budget & Reports:\n"
        "  /report — monthly summary with charts\n"
        "  /setbudget <category> <amount> — set spending limit\n"
        "  /budgets — view budget progress\n"
        "  /advice — get AI financial advice\n\n"
        "Learning & Wisdom:\n"
        "  /learn — get a financial concept\n"
        "  /quiz — take a finance quiz\n"
        "  /buddha <question> — ask the Buddha for financial wisdom\n\n"
        "Settings:\n"
        "  /setcurrency — change default currency\n"
        "  /setmonthlybudget <amount> — set total monthly limit\n"
        "  /profile — view your profile"
    )
    await update.message.reply_text(text)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    record = await repository.get_user(user_id)
    if not record:
        await update.message.reply_text("Profile not found. Use /start to register.")
        return

    accounts = await repository.get_accounts(user_id)
    budget = (
        f"{record['monthly_budget']:.2f} {record['default_currency']}"
        if record["monthly_budget"]
        else "Not set"
    )

    lines = [
        f"Name: {record['first_name']}",
        f"Default currency: {record['default_currency']}",
        f"Monthly budget: {budget}",
        f"Member since: {record['created_at'].strftime('%d %b %Y')}",
        "",
        f"Accounts ({len(accounts)}):",
    ]

    if accounts:
        for acc in accounts:
            sign = "+" if acc["balance"] >= 0 else ""
            lines.append(
                f"  {acc['name']} ({acc['account_type']}) — "
                f"{sign}{format_amount(acc['balance'], acc['currency'])}"
            )
    else:
        lines.append("  None — use /newaccount to create one")

    await update.message.reply_text("\n".join(lines))


async def cmd_set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sorted_currencies = sorted(SUPPORTED_CURRENCIES)
    buttons = [
        [
            InlineKeyboardButton(cur, callback_data=f"setcur:{cur}")
            for cur in sorted_currencies[i:i+4]
        ]
        for i in range(0, len(sorted_currencies), 4)
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "Choose your default currency (used for reports and AI advice):",
        reply_markup=reply_markup,
    )


async def callback_set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    currency = query.data.split(":")[1]
    user_id = query.from_user.id

    if currency not in SUPPORTED_CURRENCIES:
        await query.edit_message_text("Invalid currency selection.")
        return

    await repository.update_user_currency(user_id, currency)
    await query.edit_message_text(f"Default currency set to {currency}.")


async def cmd_set_monthly_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /setmonthlybudget 1500")
        return

    try:
        amount = Decimal(context.args[0].replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Please enter a valid positive amount.")
        return

    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    await repository.update_monthly_budget(user_id, amount)
    await update.message.reply_text(
        f"Monthly budget set to {amount:.2f} {user['default_currency']}."
    )