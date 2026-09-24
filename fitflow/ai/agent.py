"""The coach agent: an LLM in a loop with our tools.

How one chat turn works (the "agentic loop"):

    user message
        |
        v
    send conversation + tool definitions to Claude  <-----------------+
        |                                                              |
        v                                                              |
    Claude answers. Did it ask to use tools? (stop_reason == "tool_use")
        |-- yes: run each tool with OUR code, send the results back ---+
        |-- no:  that's the final reply -> save the turn, return it

We write this loop by hand (instead of using the SDK's tool runner) so every step is visible:
persisting the conversation, turning tool errors into feedback the model can fix, a hard cap on
rounds, and rolling back the whole turn if something fails.
"""

import json
from dataclasses import dataclass
from datetime import date

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.ai.prompts import SYSTEM_PROMPT
from fitflow.ai.tools import TOOLS, ToolExecutor
from fitflow.db import models as db

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
EFFORT = "medium"  # chat + simple tool calls don't need deep reasoning; "high" is the API default
MAX_TOOL_ROUNDS = 8  # safety net against a model stuck calling tools forever

# User-facing text is Hebrew (the app's language); code and comments stay in English.
REFUSAL_REPLY = "בזה אני לא יכול לעזור. אשמח לעזור עם תזונה, אימונים והתקדמות."
TOO_MANY_ROUNDS_REPLY = "זה דרש יותר מדי צעדים. אפשר לנסח מחדש או לפצל להודעות קצרות יותר?"


@dataclass
class AgentReply:
    text: str
    actions: list[db.PendingAction]  # proposals waiting for the user's confirmation


class CoachAgent:
    def __init__(self, client: anthropic.Anthropic):
        # The client is passed in (dependency injection) so tests can use a fake one.
        self.client = client

    def chat(self, session: Session, user: db.User, message: str, today: date, hour: int) -> AgentReply:
        history = load_history(session, user, today)
        new_messages: list[dict] = [{"role": "user", "content": message}]
        executor = ToolExecutor(session, user, today, hour)

        for _ in range(MAX_TOOL_ROUNDS):
            response = self._call_model(history + new_messages)

            if response.stop_reason == "refusal":
                # Don't save a refused turn: replaying it would only trigger the refusal again.
                session.rollback()
                return AgentReply(REFUSAL_REPLY, [])

            # Store the assistant message exactly as returned (text, tool_use, thinking blocks...).
            # The API needs these blocks replayed unchanged on the next request.
            new_messages.append({"role": "assistant", "content": [to_dict(b) for b in response.content]})

            if response.stop_reason != "tool_use":
                break  # "end_turn" (normal) or "max_tokens" (cut off - we still show what we have)

            # Run every tool the model asked for, and send ALL results back in ONE user message.
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output, is_error = executor.run(block.name, block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error})
            new_messages.append({"role": "user", "content": results})
        else:
            session.rollback()
            return AgentReply(TOO_MANY_ROUNDS_REPLY, [])

        save_messages(session, user, today, new_messages)
        session.commit()  # the turn and its pending actions are saved together, or not at all
        return AgentReply(final_text(response), executor.proposed)

    def _call_model(self, messages: list[dict]):
        return self.client.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": EFFORT},
            # Thinking is adaptive by default on this model: it decides when it needs to think.
            cache_control={"type": "ephemeral"},  # cache the growing conversation prefix -> cheaper turns
            # If the model's safety classifier declines, retry on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )


# --- helpers ---

def to_dict(block) -> dict:
    """SDK content block -> plain JSON-able dict (what we store and send back)."""
    return block.model_dump(mode="json", by_alias=True, exclude_none=True)


def final_text(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


def load_history(session: Session, user: db.User, day: date) -> list[dict]:
    """Today's conversation. A new day starts a fresh conversation, which keeps context small."""
    rows = session.scalars(
        select(db.ChatMessage)
        .where(db.ChatMessage.user_id == user.id, db.ChatMessage.day == day)
        .order_by(db.ChatMessage.id)
    )
    return [{"role": r.role, "content": json.loads(r.content)} for r in rows]


def save_messages(session: Session, user: db.User, day: date, messages: list[dict]) -> None:
    session.add_all(
        db.ChatMessage(user_id=user.id, day=day, role=m["role"], content=json.dumps(m["content"], ensure_ascii=False))
        for m in messages
    )
