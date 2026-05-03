import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.handlers_accounts import (
    callback_delete_account,
    cmd_accounts,
    cmd_delete_account,
    cmd_new_account,
)
from bot.handlers_budget import cmd_advice, cmd_budgets, cmd_report, cmd_set_budget
from bot.handlers_literacy import callback_quiz_answer, cmd_learn, cmd_quiz
from bot.handlers_transactions import (
    callback_pick_account,
    cmd_delete,
    cmd_history,
    handle_message,
)
from bot.handlers_user import (
    callback_set_currency,
    cmd_help,
    cmd_profile,
    cmd_set_currency,
    cmd_set_monthly_budget,
    cmd_start,
)
from core.scheduler import setup_scheduler
from db.database import close_pool, init_db

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def build_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("setcurrency", cmd_set_currency))
    app.add_handler(CommandHandler("setmonthlybudget", cmd_set_monthly_budget))

    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("newaccount", cmd_new_account))
    app.add_handler(CommandHandler("deleteaccount", cmd_delete_account))

    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("delete", cmd_delete))

    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("setbudget", cmd_set_budget))
    app.add_handler(CommandHandler("budgets", cmd_budgets))
    app.add_handler(CommandHandler("advice", cmd_advice))

    app.add_handler(CommandHandler("learn", cmd_learn))
    app.add_handler(CommandHandler("quiz", cmd_quiz))

    app.add_handler(CallbackQueryHandler(callback_set_currency, pattern=r"^setcur:"))
    app.add_handler(CallbackQueryHandler(callback_pick_account, pattern=r"^txacc:"))
    app.add_handler(CallbackQueryHandler(callback_delete_account, pattern=r"^delacc:"))
    app.add_handler(CallbackQueryHandler(callback_quiz_answer, pattern=r"^quiz:"))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    return app


async def main() -> None:
    await init_db()
    logger.info("Database initialized")

    app = build_application()
    scheduler = setup_scheduler(app)
    scheduler.start()
    logger.info("Scheduler started")

    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await close_pool()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())