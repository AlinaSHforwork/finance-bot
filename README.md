# Finance Bot

AI-powered financial literacy and budgeting chatbot for Telegram, guided by the wisdom of the Dharma.

## Elevator Pitch

Finance Bot helps everyday users track income and expenses, set budgets, and understand their financial behaviour — all through natural language. What sets it apart: every insight, analysis, and piece of advice is delivered through the voice of the Buddha, grounded in a curated Buddhist knowledge base. The bot implements a **RAG (Retrieval-Augmented Generation)** pattern: relevant Dharma teachings are retrieved from a local vector-free keyword knowledge base and injected into every AI prompt, ensuring that financial guidance is always rooted in specific, contextual wisdom rather than generic LLM output.

## Target Audience

- Young professionals beginning to manage their own finances
- Anyone seeking a mindful, non-anxious approach to money
- Students learning personal finance concepts in an engaging format

## AI Patterns Implemented

| Pattern | Where |
|---|---|
| **RAG** | `ai/buddhist_kb.py` — keyword-scored retrieval from 12 curated Dharma teachings; injected into every advice, analysis, learn, and `/buddha` prompt |
| **Structured Output** | `ai/client.py` — `parse_transaction` forces JSON schema output from the LLM and validates it strictly before use |
| **Multi-role prompting** | `/advice` calls two separate AI roles (spending analyst + financial advisor) and merges their outputs |

## Stack

- Python 3.11
- python-telegram-bot 20.x (async)
- PostgreSQL via asyncpg
- Gemini API (gemini-2.5-flash-lite) for NLP
- Matplotlib for charts
- APScheduler for scheduled tips

## Setup

### 1. Clone and configure

```bash
cp env.example .env
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
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Project Structure

```
finance_bot/
├── main.py
├── ai/
│   ├── buddhist_kb.py          # RAG knowledge base (12 Dharma teachings + retrieval)
│   └── client.py               # Gemini API integration with RAG injection
├── bot/
│   ├── handlers_user.py
│   ├── handlers_transactions.py
│   ├── handlers_budget.py
│   └── handlers_literacy.py    # /learn, /quiz, /buddha
├── core/
│   └── scheduler.py
├── db/
│   ├── database.py
│   └── repository.py
└── utils/
    ├── charts.py
    ├── constants.py
    └── formatters.py
```

## Commands

| Command | Description |
|---------|-------------|
| (any text) | Log a transaction via NLP |
| /start | Register |
| /help | Show all commands |
| /profile | View your profile |
| /setcurrency | Change default currency |
| /setmonthlybudget \<amount\> | Set total monthly budget |
| /history | Last 15 transactions |
| /delete \<id\> | Delete a transaction |
| /report | Monthly summary with charts |
| /setbudget \<category\> \<amount\> | Set category budget limit |
| /budgets | View budgets vs spending |
| /advice | Get AI financial advice (Buddha voice + RAG) |
| /learn | Get a financial concept (Buddha voice + RAG) |
| /quiz | Take a finance quiz |
| /buddha \<question\> | Ask the Buddha directly (RAG-grounded response) |

## How RAG Works

1. User triggers `/advice`, `/learn`, or `/buddha <question>`.
2. `search_teachings(query)` in `ai/buddhist_kb.py` scores all 12 teachings by keyword overlap with the query (tag matches weighted ×3, body text matches ×1).
3. The top-k teachings are formatted and injected into the system prompt sent to Gemini.
4. Gemini responds in the voice of the Buddha, grounded in the retrieved teachings rather than generic LLM output.

This ensures responses are consistent, on-topic, and traceable to a known knowledge base — a core property of RAG systems.