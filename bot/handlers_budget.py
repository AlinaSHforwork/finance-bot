import io
import logging
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes

from ai.client import generate_financial_advice, generate_spending_analysis
from db import repository
from utils.charts import generate_budget_bar, generate_expense_pie, generate_monthly_trend
from utils.constants import EXPENSE_CATEGORIES
from utils.formatters import (
    build_spending_summary,
    check_budget_alerts,
    current_month_range,
    format_amount,
    last_n_days,
)

logger = logging.getLogger(__name__)


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    start, end = current_month_range()
    currency = user["default_currency"]

    expense_totals = await repository.get_category_totals(user_id, start, end, "expense")
    income_totals = await repository.get_category_totals(user_id, start, end, "income")

    total_expenses = sum(r["total"] for r in expense_totals)
    total_income = sum(r["total"] for r in income_totals)

    budgets = await repository.get_budgets(user_id)
    alerts = check_budget_alerts(expense_totals, budgets, currency)

    summary_lines = [
        f"Monthly Report ({start.strftime('%b %Y')})\n",
        f"Income:   {format_amount(total_income, currency)}",
        f"Expenses: {format_amount(total_expenses, currency)}",
        f"Net:      {format_amount(total_income - total_expenses, currency)}",
    ]

    if user["monthly_budget"]:
        pct = (total_expenses / user["monthly_budget"] * 100) if user["monthly_budget"] > 0 else 0
        summary_lines.append(
            f"Budget:   {format_amount(total_expenses, currency)} / "
            f"{format_amount(user['monthly_budget'], currency)} ({pct:.0f}%)"
        )

    if alerts:
        summary_lines.append("\nAlerts:")
        summary_lines.extend(f"  {a}" for a in alerts)

    if expense_totals:
        summary_lines.append("\nExpense breakdown:")
        for row in expense_totals:
            summary_lines.append(
                f"  {row['category'].capitalize()}: {format_amount(row['total'], currency)}"
            )

    await update.message.reply_text("\n".join(summary_lines))

    if expense_totals:
        chart_data = [(r["category"], r["total"]) for r in expense_totals]
        chart_bytes = generate_expense_pie(chart_data, currency)
        if chart_bytes:
            await update.message.reply_photo(
                photo=io.BytesIO(chart_bytes),
                caption="Expense distribution this month",
            )

    if budgets and expense_totals:
        budget_spent_map = {r["category"]: r["total"] for r in expense_totals}
        budget_data = [
            (b["category"], b["monthly_limit"], budget_spent_map.get(b["category"], Decimal("0")))
            for b in budgets
        ]
        bar_bytes = generate_budget_bar(budget_data, currency)
        if bar_bytes:
            await update.message.reply_photo(
                photo=io.BytesIO(bar_bytes),
                caption="Budget vs actual spending",
            )


async def cmd_set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        cats = ", ".join(EXPENSE_CATEGORIES)
        await update.message.reply_text(
            f"Usage: /setbudget <category> <amount>\n"
            f"Categories: {cats}\n"
            f"Example: /setbudget food 300"
        )
        return

    category = context.args[0].lower()
    if category not in EXPENSE_CATEGORIES:
        await update.message.reply_text(
            f"Unknown category '{category}'.\n"
            f"Valid categories: {', '.join(EXPENSE_CATEGORIES)}"
        )
        return

    try:
        amount = Decimal(context.args[1].replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await update.message.reply_text("Please provide a valid positive amount.")
        return

    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    await repository.set_category_budget(user_id, category, amount)
    await update.message.reply_text(
        f"Budget for {category.capitalize()} set to {format_amount(amount, user['default_currency'])} per month."
    )


async def cmd_budgets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    budgets = await repository.get_budgets(user_id)
    if not budgets:
        await update.message.reply_text(
            "No category budgets set yet.\nUse /setbudget <category> <amount>"
        )
        return

    start, end = current_month_range()
    expense_totals = await repository.get_category_totals(user_id, start, end, "expense")
    spent_map = {r["category"]: r["total"] for r in expense_totals}
    currency = user["default_currency"]

    lines = ["Your budgets this month:\n"]
    for b in budgets:
        cat = b["category"]
        limit = b["monthly_limit"]
        spent = spent_map.get(cat, Decimal("0"))
        pct = (spent / limit * 100) if limit > 0 else 0
        bar = "#" * int(pct / 10) + "-" * (10 - int(min(pct, 100) / 10))
        status = "OVER" if pct > 100 else f"{pct:.0f}%"
        lines.append(
            f"{cat.capitalize()}: [{bar}] {status}\n"
            f"  {format_amount(spent, currency)} / {format_amount(limit, currency)}"
        )

    await update.message.reply_text("\n".join(lines))


async def cmd_advice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    thinking = await update.message.reply_text("Analyzing your finances...")

    start, end = current_month_range()
    currency = user["default_currency"]

    expense_totals = await repository.get_category_totals(user_id, start, end, "expense")
    income_totals = await repository.get_category_totals(user_id, start, end, "income")
    budgets = await repository.get_budgets(user_id)

    total_income = sum(r["total"] for r in income_totals)
    total_expenses = sum(r["total"] for r in expense_totals)

    spending_summary = build_spending_summary(
        expense_totals, currency, total_income, total_expenses
    )
    alerts = check_budget_alerts(expense_totals, budgets, currency)

    try:
        advice = await generate_financial_advice(
            user_name=user["first_name"],
            currency=currency,
            spending_summary=spending_summary,
            monthly_budget=user["monthly_budget"],
            budget_alerts=alerts,
            accounts=await repository.get_accounts(user_id),
        )
        analysis = await generate_spending_analysis(
            currency=currency,
            category_totals=[(r["category"], r["total"]) for r in expense_totals],
            income_total=total_income,
            expense_total=total_expenses,
        )
        await thinking.edit_text(f"Financial Analysis:\n\n{analysis}\n\nPersonalized Tips:\n\n{advice}")
    except Exception as exc:
        logger.error("generate_financial_advice failed: %s", exc)
        await thinking.edit_text("Could not generate advice at this time. Please try again later.")
