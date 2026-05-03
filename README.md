# Finance Bot

AI-powered financial literacy and budgeting chatbot for Telegram.

## Stack

- Python 3.11
- python-telegram-bot 20.x (async)
- PostgreSQL via asyncpg
- Gemini API (xAI) for NLP
- Matplotlib for charts
- APScheduler for scheduled tips

## Setup

### 1. Clone and configure

```bash
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=<your bot token from @BotFather>
GEMINI_API_KEY=<your Gemini API key>
DATABASE_URL=postgresql://user:password@localhost:5432/finance_bot
```

### 2. Run with Docker Compose (recommended)

```bash
docker compose up -d
```

### 3. Run locally

```bash
# Create and activate virtualenv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL separately, then run:
python main.py
```

## Project Structure

```
finance_bot/
├── main.py                     # Entry point, bot setup
├── ai/
│   └── client.py               # Gemini API integration
├── bot/
│   ├── handlers_user.py        # Registration, settings
│   ├── handlers_transactions.py# NLP transaction logging
│   ├── handlers_budget.py      # Reports, budgets, advice
│   └── handlers_literacy.py    # Quiz and learn commands
├── core/
│   └── scheduler.py            # Daily tips scheduler
├── db/
│   ├── database.py             # Connection pool, schema init
│   └── repository.py           # All DB queries
└── utils/
    ├── charts.py               # Matplotlib chart generation
    ├── constants.py            # Categories, currencies, topics
    └── formatters.py           # Text formatting helpers
```

## Features

- Natural language transaction logging ("spent $20 on coffee")
- Expense and income tracking with categories
- Per-category budget limits with visual progress bars
- Monthly reports with pie charts and bar charts
- AI-generated personalized financial advice
- Financial literacy concepts on demand
- AI-generated multiple-choice quizzes
- Daily scheduled financial tips (9:00 UTC)
- Multi-currency support

## Commands

| Command | Description |
|---------|-------------|
| (any text) | Log a transaction via NLP |
| /start | Register |
| /help | Show all commands |
| /profile | View your profile |
| /setcurrency | Change default currency |
| /setmonthlybudget <amount> | Set total monthly budget |
| /history | Last 15 transactions |
| /delete <id> | Delete a transaction |
| /report | Monthly summary with charts |
| /setbudget <category> <amount> | Set category budget limit |
| /budgets | View budgets vs spending |
| /advice | Get AI financial advice |
| /learn | Get a financial concept |
| /quiz | Take a finance quiz |
