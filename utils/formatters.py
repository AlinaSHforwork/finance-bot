from datetime import date, timedelta
from decimal import Decimal
from typing import Optional


def format_amount(amount: Decimal, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def current_month_range() -> tuple[date, date]:
    today = date.today()
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return start, end


def last_n_days(n: int) -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=n - 1), today


def escape_md(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


def truncate(text: str, max_len: int = 50) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def build_spending_summary(
    category_totals: list,
    currency: str,
    income_total: Decimal,
    expense_total: Decimal,
) -> str:
    lines = [
        f"Income: {format_amount(income_total, currency)}",
        f"Expenses: {format_amount(expense_total, currency)}",
        f"Net: {format_amount(income_total - expense_total, currency)}",
        "",
        "Expense breakdown:",
    ]
    for row in category_totals:
        lines.append(f"  {row['category'].capitalize()}: {format_amount(row['total'], currency)}")
    return "\n".join(lines)


def check_budget_alerts(
    category_totals: list,
    budgets: list,
    currency: str,
) -> list[str]:
    budget_map = {b["category"]: b["monthly_limit"] for b in budgets}
    alerts = []
    for row in category_totals:
        cat = row["category"]
        spent = row["total"]
        if cat in budget_map:
            limit = budget_map[cat]
            pct = (spent / limit * 100) if limit > 0 else 0
            if pct >= 100:
                alerts.append(
                    f"OVER BUDGET in {cat.capitalize()}: spent {format_amount(spent, currency)} "
                    f"of {format_amount(limit, currency)} ({pct:.0f}%)"
                )
            elif pct >= 80:
                alerts.append(
                    f"Warning - {cat.capitalize()}: {pct:.0f}% of budget used "
                    f"({format_amount(spent, currency)} / {format_amount(limit, currency)})"
                )
    return alerts