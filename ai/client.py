import json
import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig


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

    system = (
        "You are a friendly and practical personal finance advisor. "
        "Analyze spending data and provide concise, actionable advice. "
        "Keep the response under 200 words. Use bullet points. Be specific and encouraging."
    )

    user_msg = (
        f"User: {user_name}\n"
        f"Currency: {currency}\n"
        f"{budget_info}\n"
        f"Budget alerts:\n{alerts_info}\n"
        f"Spending this month:\n{spending_summary}\n\n"
        f"Accounts:\n{accounts_info}\n\n"
        "Provide 3-5 personalized financial tips based on this data."
    )

    return await _chat(system, user_msg, temperature=0.7, max_tokens=400)


async def generate_spending_analysis(
    currency: str,
    category_totals: list[tuple[str, Decimal]],
    income_total: Decimal,
    expense_total: Decimal,
) -> str:
    totals_text = "\n".join(
        f"- {cat}: {amount:.2f} {currency}" for cat, amount in category_totals
    )

    system = (
        "You are a concise financial analyst. Identify spending patterns and provide "
        "2-3 key observations. Keep response under 150 words. Be direct and factual."
    )

    user_msg = (
        f"Monthly summary:\n"
        f"Total income: {income_total:.2f} {currency}\n"
        f"Total expenses: {expense_total:.2f} {currency}\n"
        f"Net: {income_total - expense_total:.2f} {currency}\n"
        f"Expense breakdown:\n{totals_text}\n\n"
        "What are the key observations about this spending pattern?"
    )

    return await _chat(system, user_msg, temperature=0.5, max_tokens=300)


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
    system = (
        "You are a financial educator. Explain personal finance concepts clearly and concisely "
        "for beginners. Keep explanations under 120 words. Use simple language and one practical example."
    )

    return await _chat(
        system,
        f"Explain the concept of '{concept_key}' in personal finance.",
        temperature=0.6,
        max_tokens=200,
    )