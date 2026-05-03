from datetime import date
from decimal import Decimal
from typing import Optional

import asyncpg

from db.database import get_pool


async def upsert_user(
    user_id: int,
    username: Optional[str],
    first_name: str,
) -> None:
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO users (id, username, first_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_active = NOW()
    """, user_id, username, first_name)


async def get_user(user_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow("SELECT * FROM users WHERE id = $1", user_id)


async def update_user_currency(user_id: int, currency: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET default_currency = $1 WHERE id = $2",
        currency.upper(), user_id,
    )


async def update_monthly_budget(user_id: int, amount: Decimal) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET monthly_budget = $1 WHERE id = $2",
        amount, user_id,
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

async def create_account(
    user_id: int,
    name: str,
    account_type: str,
    currency: str,
    initial_balance: Decimal = Decimal("0"),
) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    try:
        return await pool.fetchrow("""
            INSERT INTO accounts (user_id, name, account_type, currency, balance)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """, user_id, name.strip(), account_type, currency.upper(), initial_balance)
    except asyncpg.UniqueViolationError:
        return None


async def get_accounts(user_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM accounts WHERE user_id = $1 ORDER BY name",
        user_id,
    )


async def get_account(user_id: int, account_id: int) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM accounts WHERE id = $1 AND user_id = $2",
        account_id, user_id,
    )


async def get_account_by_name(user_id: int, name: str) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM accounts WHERE user_id = $1 AND LOWER(name) = LOWER($2)",
        user_id, name.strip(),
    )


async def delete_account(user_id: int, account_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM accounts WHERE id = $1 AND user_id = $2",
        account_id, user_id,
    )
    return result == "DELETE 1"


async def update_account_balance(
    account_id: int,
    delta: Decimal,
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    executor = conn or await get_pool()
    await executor.execute(
        "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
        delta, account_id,
    )


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

async def add_transaction(
    user_id: int,
    account_id: int,
    amount: Decimal,
    category: str,
    description: Optional[str],
    transaction_type: str,
    transaction_date: date,
    raw_input: Optional[str] = None,
) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                INSERT INTO transactions
                    (user_id, account_id, amount, category, description,
                     transaction_type, transaction_date, raw_input)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, user_id, account_id, amount, category.lower(), description,
                transaction_type, transaction_date, raw_input)

            delta = amount if transaction_type == "income" else -amount
            await conn.execute(
                "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
                delta, account_id,
            )
    return row["id"]


async def delete_transaction(user_id: int, transaction_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            tx = await conn.fetchrow(
                "SELECT * FROM transactions WHERE id = $1 AND user_id = $2",
                transaction_id, user_id,
            )
            if not tx:
                return False

            await conn.execute(
                "DELETE FROM transactions WHERE id = $1",
                transaction_id,
            )

            if tx["account_id"]:
                delta = -tx["amount"] if tx["transaction_type"] == "income" else tx["amount"]
                await conn.execute(
                    "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
                    delta, tx["account_id"],
                )
    return True


async def get_transactions(
    user_id: int,
    account_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    transaction_type: Optional[str] = None,
    limit: int = 50,
) -> list[asyncpg.Record]:
    pool = await get_pool()
    conditions = ["t.user_id = $1"]
    params: list = [user_id]
    idx = 2

    if account_id is not None:
        conditions.append(f"t.account_id = ${idx}")
        params.append(account_id)
        idx += 1
    if start_date:
        conditions.append(f"t.transaction_date >= ${idx}")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"t.transaction_date <= ${idx}")
        params.append(end_date)
        idx += 1
    if transaction_type:
        conditions.append(f"t.transaction_type = ${idx}")
        params.append(transaction_type)
        idx += 1

    params.append(limit)
    where = " AND ".join(conditions)
    return await pool.fetch(f"""
        SELECT t.*, a.name AS account_name, a.currency AS account_currency
        FROM transactions t
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE {where}
        ORDER BY t.transaction_date DESC, t.created_at DESC
        LIMIT ${idx}
    """, *params)


async def get_category_totals(
    user_id: int,
    start_date: date,
    end_date: date,
    transaction_type: str = "expense",
) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch("""
        SELECT category, SUM(amount) as total
        FROM transactions
        WHERE user_id = $1
          AND transaction_date BETWEEN $2 AND $3
          AND transaction_type = $4
        GROUP BY category
        ORDER BY total DESC
    """, user_id, start_date, end_date, transaction_type)


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

async def set_category_budget(user_id: int, category: str, limit: Decimal) -> None:
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO budgets (user_id, category, monthly_limit)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, category) DO UPDATE SET
            monthly_limit = EXCLUDED.monthly_limit,
            updated_at = NOW()
    """, user_id, category.lower(), limit)


async def get_budgets(user_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM budgets WHERE user_id = $1 ORDER BY category",
        user_id,
    )


# ---------------------------------------------------------------------------
# Literacy / quiz
# ---------------------------------------------------------------------------

async def save_quiz_progress(user_id: int, topic: str, correct: bool) -> None:
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO quiz_progress (user_id, topic, score, attempts, last_quiz_at)
        VALUES ($1, $2, $3::int, 1, NOW())
        ON CONFLICT (user_id, topic) DO UPDATE SET
            score = quiz_progress.score + $3::int,
            attempts = quiz_progress.attempts + 1,
            last_quiz_at = NOW()
    """, user_id, topic, 1 if correct else 0)


async def mark_literacy_sent(user_id: int, concept_key: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO literacy_sent (user_id, concept_key) VALUES ($1, $2)",
        user_id, concept_key,
    )


async def get_sent_literacy_keys(user_id: int) -> set[str]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT concept_key FROM literacy_sent WHERE user_id = $1",
        user_id,
    )
    return {row["concept_key"] for row in rows}