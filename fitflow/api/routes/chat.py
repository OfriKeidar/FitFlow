from datetime import datetime

import anthropic
from fastapi import APIRouter, HTTPException

from fitflow.ai.agent import load_history
from fitflow.api.deps import DB, Agent, CurrentUser, Today
from fitflow.api.schemas import ChatHistoryItem, ChatIn, ChatOut, PendingActionOut
from fitflow.services import actions

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatOut)
def send_message(body: ChatIn, user: CurrentUser, db: DB, today: Today, agent: Agent):
    hour = datetime.now().hour if body.hour is None else body.hour
    try:
        reply = agent.chat(db, user, body.message, today, hour)
    except anthropic.RateLimitError:
        db.rollback()
        raise HTTPException(429, "The coach is busy right now, try again in a minute")
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        # The SDK already retried; this is a real outage or a config problem (e.g. missing API key).
        db.rollback()
        raise HTTPException(503, "The coach is unavailable right now")
    return ChatOut(reply=reply.text, actions=[PendingActionOut.model_validate(a) for a in reply.actions])


@router.get("/history", response_model=list[ChatHistoryItem])
def history(user: CurrentUser, db: DB, today: Today):
    """Today's conversation as the user sees it: only visible text, no tool calls or results."""
    items = []
    for message in load_history(db, user, today):
        content = message["content"]
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(b["text"] for b in content if b.get("type") == "text")
        if text.strip():
            items.append(ChatHistoryItem(role=message["role"], text=text))
    return items


@router.post("/actions/{action_id}/confirm", response_model=PendingActionOut)
def confirm_action(action_id: int, user: CurrentUser, db: DB):
    action = _pending_or_404(db, user, action_id)
    try:
        actions.confirm(db, user, action)
    except actions.ActionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    return action


@router.post("/actions/{action_id}/reject", response_model=PendingActionOut)
def reject_action(action_id: int, user: CurrentUser, db: DB):
    action = _pending_or_404(db, user, action_id)
    actions.reject(db, action)
    return action


def _pending_or_404(db: DB, user: CurrentUser, action_id: int):
    # 404 also for already-confirmed actions: confirming twice must never log twice.
    action = actions.get_pending(db, user, action_id)
    if action is None:
        raise HTTPException(404, "No pending action with this id")
    return action
