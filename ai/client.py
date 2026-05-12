import json
import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ai.buddhist_kb import format_context, search_teachings


@dataclass
class ParsedTransaction:
    amount: Decimal
    category: str
    description: str
    transaction_type: str
    transaction_date: date
    confidence: float
    account_name: Optional[str] = field(default=None)


_model: Optional[genai.GenerativeModel] = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-2.5-flash-lite")
    return _model


async def _chat(
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    model = _get_model()
    config = GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    prompt = f"{system}\n\n{user}"
    response = await model.generate_content_async(
        prompt,
        generation_config=config,
    )
    return response.text.strip()


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


async def parse_transaction(
    text: str,
    user_currency: str,
    today: date,
    account_names: Optional[list[str]] = None,
) -> Optional[ParsedTransaction]:
    accounts_hint = ""
    if account_names:
        names_list = ", ".join(f'"{n}"' for n in account_names)
        accounts_hint = (
            f"The user has these accounts: [{names_list}]. "
            "If the message mentions one of these account names (e.g. 'from Cash', 'to MyCard'), "
            'set "account_name" to the exact matching name. Otherwise set "account_name" to null. '
        )

    system = (
        "You are a financial transaction parser. Extract transaction details from user input. "
        "Respond ONLY with valid JSON, no markdown, no explanation. "
        "JSON schema: {"
        '"amount": number, '
        '"category": string, '
        '"description": string, '
        '"transaction_type": "expense" or "income", '
        '"transaction_date": "YYYY-MM-DD", '
        '"account_name": string or null, '
        '"confidence": number between 0 and 1'
        "} "
        f"Today is {today.isoformat()}. User default currency is {user_currency}. "
        f"{accounts_hint}"
        "Categories: food, transport, shopping, entertainment, health, education, utilities, salary, freelance, investment, other. "
        "If the input is not a financial transaction, return null."
    )

    raw = await _chat(system, text, temperature=0.1, max_tokens=300)
    raw = _strip_fences(raw)

    if raw.lower() in ("null", "none", ""):
        return None

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return None

    required = {"amount", "category", "description", "transaction_type", "transaction_date", "confidence"}
    if not required.issubset(data.keys()):
        return None

    if data["transaction_type"] not in ("expense", "income"):
        return None

    try:
        tx_date = date.fromisoformat(data["transaction_date"])
    except (ValueError, TypeError):
        tx_date = today

    raw_account = data.get("account_name")
    account_name: Optional[str] = None
    if raw_account and account_names:
        match = next(
            (n for n in account_names if n.lower() == str(raw_account).lower()),
            None,
        )
        account_name = match

    return ParsedTransaction(
        amount=Decimal(str(abs(float(data["amount"])))),
        category=str(data["category"]).lower().strip(),
        description=str(data["description"]).strip(),
        transaction_type=data["transaction_type"],
        transaction_date=tx_date,
        confidence=float(data.get("confidence", 0.5)),
        account_name=account_name,
    )


async def generate_financial_advice(
    user_name: str,
    currency: str,
    spending_summary: str,
    monthly_budget: Optional[Decimal],
    budget_alerts: list[str],
    accounts: list[dict[str, Any]],
) -> str:
    budget_info = f"Monthly budget: {monthly_budget} {currency}" if monthly_budget else "No monthly budget set."
    alerts_info = "\n".join(budget_alerts) if budget_alerts else "No budget exceeded."
    accounts_info = "\n".join(f"- {acc['name']}: {acc['balance']} {currency}" for acc in accounts) if accounts else "No accounts found."

    rag_query = f"budget advice spending {' '.join(a.split(':')[0].lower() for a in budget_alerts) if budget_alerts else 'balance generosity savings'}"
    teachings = search_teachings(rag_query, top_k=2)
    dharma_context = format_context(teachings)

    system = (
        "You are the Buddha — compassionate, calm, and deeply wise. "
        "You speak in the voice of the Awakened One: gentle, clear, unhurried, with occasional Pali terms explained simply. "
        "You frame financial guidance through the lens of the Dharma: the Middle Way, impermanence, non-attachment, and right livelihood. "
        "You never mock or shame. You offer practical steps wrapped in spiritual insight. "
        "Keep the response under 220 words. Use short paragraphs, no bullet points."
    )

    user_msg = (
        f"Seeker's name: {user_name}\n"
        f"Currency: {currency}\n"
        f"{budget_info}\n"
        f"Budget alerts:\n{alerts_info}\n"
        f"Spending this month:\n{spending_summary}\n\n"
        f"Accounts:\n{accounts_info}\n\n"
        f"Relevant Dharma teachings for context:\n{dharma_context}\n\n"
        "Offer 3-5 personalized pieces of financial wisdom rooted in Buddhist teaching."
    )

    return await _chat(system, user_msg, temperature=0.7, max_tokens=450)


async def generate_spending_analysis(
    currency: str,
    category_totals: list[tuple[str, Decimal]],
    income_total: Decimal,
    expense_total: Decimal,
) -> str:
    categories_str = " ".join(cat for cat, _ in category_totals)
    teachings = search_teachings(f"report reflection {categories_str}", top_k=2)
    dharma_context = format_context(teachings)

    totals_text = "\n".join(
        f"- {cat}: {amount:.2f} {currency}" for cat, amount in category_totals
    )

    system = (
        "You are the Buddha — compassionate, calm, and deeply wise. "
        "You speak in the voice of the Awakened One: gentle, clear, with occasional Pali terms explained simply. "
        "You observe financial patterns with equanimity, neither praising nor condemning. "
        "You see in numbers the story of the mind's cravings and wisdom. "
        "Keep response under 160 words. Use short paragraphs."
    )

    user_msg = (
        f"Monthly summary:\n"
        f"Total income: {income_total:.2f} {currency}\n"
        f"Total expenses: {expense_total:.2f} {currency}\n"
        f"Net: {income_total - expense_total:.2f} {currency}\n"
        f"Expense breakdown:\n{totals_text}\n\n"
        f"Relevant Dharma teachings:\n{dharma_context}\n\n"
        "What patterns do you observe in this seeker's financial conduct?"
    )

    return await _chat(system, user_msg, temperature=0.5, max_tokens=320)


async def generate_buddha_wisdom(
    query: str,
    user_currency: str,
    spending_context: Optional[str] = None,
) -> str:
    teachings = search_teachings(query, top_k=3)
    dharma_context = format_context(teachings)

    system = (
        "You are the Buddha — compassionate, calm, and deeply wise. "
        "You speak in the voice of the Awakened One: gentle, clear, unhurried, with occasional Pali or Sanskrit terms explained simply. "
        "You address questions about money, spending, debt, saving, and wealth through the lens of the Dharma. "
        "You do not give dry financial advice; you illuminate the mind that relates to money. "
        "You never shame the seeker. You always point toward liberation. "
        "Keep response under 180 words."
    )

    context_block = f"Seeker's spending context: {spending_context}\n\n" if spending_context else ""

    user_msg = (
        f"{context_block}"
        f"Relevant Dharma teachings from the knowledge base:\n{dharma_context}\n\n"
        f"Seeker's question: {query}\n\n"
        "Respond as the Buddha, grounding your answer in the provided teachings."
    )

    return await _chat(system, user_msg, temperature=0.75, max_tokens=400)


async def generate_quiz_question(topic: str) -> Optional[dict[str, Any]]:
    system = (
        "You are a financial literacy quiz creator. "
        "Create a multiple-choice question about personal finance. "
        "Respond ONLY with valid JSON. No markdown. "
        "Schema: {"
        '"question": string, '
        '"options": ["A) ...", "B) ...", "C) ...", "D) ..."], '
        '"correct": "A" or "B" or "C" or "D", '
        '"explanation": string'
        "}"
    )

    raw = await _chat(
        system,
        f"Create a {topic} quiz question for someone learning personal finance basics.",
        temperature=0.8,
        max_tokens=350,
    )

    raw = _strip_fences(raw)

    try:
        data = json.loads(raw)
        required = {"question", "options", "correct", "explanation"}
        if not required.issubset(data.keys()):
            return None
        if len(data["options"]) != 4:
            return None
        return data
    except (json.JSONDecodeError, KeyError):
        return None


async def get_literacy_concept(concept_key: str) -> str:
    teachings = search_teachings(concept_key, top_k=1)
    dharma_context = format_context(teachings)

    system = (
        "You are the Buddha — compassionate, calm, and deeply wise. "
        "You explain personal finance concepts by weaving together practical clarity and Dharma wisdom. "
        "Keep explanations under 140 words. Use simple language and one practical example. "
        "End with a short reflection rooted in Buddhist teaching."
    )

    context_block = f"Related Dharma teaching:\n{dharma_context}\n\n" if dharma_context else ""

    return await _chat(
        system,
        f"{context_block}Explain the personal finance concept of '{concept_key}'.",
        temperature=0.6,
        max_tokens=220,
    )