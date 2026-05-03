import logging
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from ai.client import get_literacy_concept
from db.database import get_pool
from db.repository import mark_literacy_sent
from utils.constants import LITERACY_CONCEPTS

logger = logging.getLogger(__name__)


async def send_daily_tips(app: Application) -> None:
    try:
        pool = await get_pool()
    except Exception as exc:
        logger.error("Cannot connect to DB for daily tips: %s", exc)
        return

    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT id FROM users WHERE last_active > NOW() - INTERVAL '7 days'"
        )

    if not users:
        return

    concept_key = random.choice(LITERACY_CONCEPTS)

    try:
        explanation = await get_literacy_concept(concept_key)
    except Exception as exc:
        logger.error("Daily tip AI generation failed: %s", exc)
        return

    message = (
        f"Daily Finance Tip: {concept_key.title()}\n\n"
        f"{explanation}\n\n"
        f"Use /learn for more concepts or /quiz to test your knowledge."
    )

    for user in users:
        try:
            await app.bot.send_message(chat_id=user["id"], text=message)
            await mark_literacy_sent(user["id"], concept_key)
        except Exception as exc:
            logger.warning("Failed to send tip to user %s: %s", user["id"], exc)


def setup_scheduler(app: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        send_daily_tips,
        trigger="cron",
        hour=9,
        minute=0,
        args=[app],
        id="daily_tips",
        replace_existing=True,
    )
    return scheduler
