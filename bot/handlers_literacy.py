import logging
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ai.client import generate_quiz_question, get_literacy_concept
from db import repository
from utils.constants import LITERACY_CONCEPTS, QUIZ_TOPICS

logger = logging.getLogger(__name__)


async def cmd_learn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    sent_keys = await repository.get_sent_literacy_keys(user_id)
    available = [c for c in LITERACY_CONCEPTS if c not in sent_keys]

    if not available:
        available = LITERACY_CONCEPTS

    concept_key = random.choice(available)

    thinking = await update.message.reply_text("Loading concept...")

    try:
        explanation = await get_literacy_concept(concept_key)
        await thinking.edit_text(
            f"Financial Concept: {concept_key.title()}\n\n{explanation}"
        )
        await repository.mark_literacy_sent(user_id, concept_key)
    except Exception as exc:
        logger.error("get_literacy_concept failed: %s", exc)
        await thinking.edit_text("Could not load concept right now. Please try again.")


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await repository.get_user(user_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    topic = random.choice(QUIZ_TOPICS)
    thinking = await update.message.reply_text("Generating quiz question...")

    try:
        question_data = await generate_quiz_question(topic)
    except Exception as exc:
        logger.error("generate_quiz_question failed: %s", exc)
        await thinking.edit_text("Could not generate quiz right now. Please try again.")
        return

    if not question_data:
        await thinking.edit_text("Failed to generate a valid quiz question. Please try again.")
        return

    context.user_data["active_quiz"] = {
        "topic": topic,
        "correct": question_data["correct"],
        "explanation": question_data["explanation"],
    }

    buttons = [
        [InlineKeyboardButton(opt, callback_data=f"quiz:{opt[0]}")]
        for opt in question_data["options"]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    quiz_text = f"Topic: {topic.title()}\n\n{question_data['question']}"
    await thinking.edit_text(quiz_text, reply_markup=reply_markup)


async def callback_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    selected = query.data.split(":")[1]

    quiz_data = context.user_data.pop("active_quiz", None)
    if not quiz_data:
        await query.edit_message_text("Quiz session expired. Use /quiz to start a new one.")
        return

    correct_letter = quiz_data["correct"]
    is_correct = selected == correct_letter

    await repository.save_quiz_progress(
        user_id=user_id,
        topic=quiz_data["topic"],
        correct=is_correct,
    )

    result_text = "Correct!" if is_correct else f"Incorrect. The correct answer was {correct_letter}."
    full_text = (
        f"{query.message.text}\n\n"
        f"Your answer: {selected}\n"
        f"{result_text}\n\n"
        f"Explanation: {quiz_data['explanation']}\n\n"
        f"Use /quiz for another question or /learn for a new concept."
    )

    await query.edit_message_text(full_text)
