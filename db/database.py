import asyncpg
import os
from typing import Optional


_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.getenv("DATABASE_URL"),
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                default_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                monthly_budget NUMERIC(12, 2),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_active TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                account_type VARCHAR(20) NOT NULL DEFAULT 'other',
                currency VARCHAR(3) NOT NULL,
                balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, name)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
                amount NUMERIC(12, 2) NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('expense', 'income', 'transfer')),
                transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
                raw_input TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_user_date
            ON transactions(user_id, transaction_date DESC)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_account
            ON transactions(account_id)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                monthly_limit NUMERIC(12, 2) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, category)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quiz_progress (
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                topic TEXT NOT NULL,
                score INT NOT NULL DEFAULT 0,
                attempts INT NOT NULL DEFAULT 0,
                last_quiz_at TIMESTAMPTZ,
                PRIMARY KEY (user_id, topic)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS literacy_sent (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                concept_key TEXT NOT NULL,
                sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)