"""The coach agent: an LLM in a loop with our tools.

How one chat turn works (the "agentic loop"):

    user message
        |
        v
    send conversation + tool definitions to the model  <--------------+
        |                                                              |
        v                                                              |
    The model answers. Did it ask to use tools?                        |
        |-- yes: run each tool with OUR code, send the results back ---+
        |-- no:  that's the final reply -> save the turn, return it

We write this loop by hand (instead of an SDK's tool runner) so every step is visible:
persisting the conversation, turning tool errors into feedback the model can fix, a hard cap on
rounds, and rolling back the whole turn if something fails.

The loop doesn't know which model it talks to - see providers.py (Claude, Gemini, ...).
"""

import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.ai.prompts import SYSTEM_PROMPT
from fitflow.ai.providers import LLMProvider, ToolResult
from fitflow.ai.tools import TOOLS, ToolExecutor
from fitflow.db import models as db

MAX_TOOL_ROUNDS = 8  # safety net against a model stuck calling tools forever

# User-facing text is Hebrew (the app's language); code and comments stay in English.
REFUSAL_REPLY = "בזה אני לא יכול לעזור. אשמח לעזור עם תזונה, אימונים והתקדמות."
TOO_MANY_ROUNDS_REPLY = "זה דרש יותר מדי צעדים. אפשר לנסח מחדש או לפצל להודעות קצרות יותר?"


@dataclass
class AgentReply:
    text: str
    actions: list[db.PendingAction]  # proposals waiting for the user's confirmation


class CoachAgent:
    def __init__(self, llm: LLMProvider):
        # The provider is passed in (dependency injection): Claude, Gemini, or a fake in tests.
        # One agent serves all users at once, so per-user data is passed as arguments, never stored on self.
        self.llm = llm

    def chat(self, session: Session, user: db.User, message: str, today: date, hour: int) -> AgentReply:
        history = load_history(session, user, today, provider=self.llm.name)
        new_messages: list[dict] = [{"role": "user", "content": message}]
        executor = ToolExecutor(session, user, today, hour)

        for _ in range(MAX_TOOL_ROUNDS):
            turn = self.llm.complete(SYSTEM_PROMPT, user_context(user), history + new_messages, TOOLS)

            if turn.refused:
                # Don't save a refused turn: replaying it would only trigger the refusal again.
                session.rollback()
                return AgentReply(REFUSAL_REPLY, [])

            new_messages.append(turn.message)
            if not turn.tool_calls:
                break  # a final answer

            # Run every tool the model asked for, and send ALL the results back together.
            results = []
            for call in turn.tool_calls:
                if call.input is None:
                    results.append(ToolResult(call.id, "The arguments were not valid JSON. Try again.", True))
                else:
                    output, is_error = executor.run(call.name, call.input)
                    results.append(ToolResult(call.id, output, is_error))
            new_messages.extend(self.llm.tool_results(results))
        else:
            session.rollback()
            return AgentReply(TOO_MANY_ROUNDS_REPLY, [])

        save_messages(session, user, today, self.llm.name, new_messages)
        session.commit()  # the turn and its pending actions are saved together, or not at all
        return AgentReply(turn.text, executor.proposed)


def user_context(user: db.User) -> str:
    """Per-user facts for the model. In Hebrew, verbs and adjectives change with gender ("תאשר" /
    "תאשרי"), and guessing it from the name goes wrong - so we tell the model explicitly."""
    form = "feminine" if user.sex == "female" else "masculine"
    return f"The user's name is {user.name}. Address them in {form} Hebrew forms."


# --- conversation storage ---

def load_history(session: Session, user: db.User, day: date, provider: str | None = None) -> list[dict]:
    """Today's conversation (a new day starts fresh, which keeps the context small).

    With `provider`, only that provider's messages: tool calls are stored in each API's own format,
    so a conversation can only be continued by the provider that wrote it.
    """
    query = select(db.ChatMessage).where(db.ChatMessage.user_id == user.id, db.ChatMessage.day == day)
    if provider is not None:
        query = query.where(db.ChatMessage.provider == provider)
    return [json.loads(row.content) for row in session.scalars(query.order_by(db.ChatMessage.id))]


def save_messages(session: Session, user: db.User, day: date, provider: str, messages: list[dict]) -> None:
    session.add_all(
        db.ChatMessage(user_id=user.id, day=day, provider=provider, role=m["role"],
                       content=json.dumps(m, ensure_ascii=False))
        for m in messages
    )


def visible_text(message: dict) -> str:
    """The part of a stored message a person should see (no tool calls, no tool results)."""
    if message.get("role") not in ("user", "assistant"):
        return ""  # e.g. OpenAI-style "tool" messages
    content = message.get("content")
    if isinstance(content, str):
        return content
    # Anthropic-style list of blocks; a user message made of tool_result blocks has no text.
    return "\n".join(b.get("text", "") for b in content or [] if b.get("type") == "text")
