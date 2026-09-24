"""Shared FastAPI dependencies."""

from datetime import date
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from fitflow.db.models import User
from fitflow.db.session import get_db

DB = Annotated[Session, Depends(get_db)]


def get_today() -> date:
    """A dependency (not date.today() inline) so tests can travel in time."""
    return date.today()


Today = Annotated[date, Depends(get_today)]


def get_current_user(db: DB, x_user_id: Annotated[int, Header()]) -> User:
    # TODO(auth): replace the X-User-Id header with JWT login before deploying.
    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
