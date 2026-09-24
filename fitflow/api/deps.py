"""Shared FastAPI dependencies."""

from datetime import date
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from fitflow.ai.agent import CoachAgent
from fitflow.ai.providers import LLMNotConfigured, provider_from_env
from fitflow.db.models import User
from fitflow.db.session import get_db
from fitflow.services import auth

DB = Annotated[Session, Depends(get_db)]


def get_today() -> date:
    """A dependency (not date.today() inline) so tests can travel in time."""
    return date.today()


Today = Annotated[date, Depends(get_today)]


bearer = HTTPBearer(auto_error=False)  # reads "Authorization: Bearer <token>"


def get_current_user(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    """Every protected endpoint depends on this: no valid token -> 401, and the handler never runs."""
    user_id = auth.user_id_from_token(credentials.credentials) if credentials else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@lru_cache
def _shared_agent() -> CoachAgent:
    """One agent for the whole app, using the provider configured in the environment (see providers.py)."""
    return CoachAgent(provider_from_env())


def get_agent() -> CoachAgent:
    try:
        return _shared_agent()  # a failure isn't cached, so setting a key later works without a restart
    except LLMNotConfigured as e:
        raise HTTPException(503, f"The coach is not configured: {e}")


Agent = Annotated[CoachAgent, Depends(get_agent)]
