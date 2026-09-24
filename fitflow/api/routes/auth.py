from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from fitflow.api.deps import DB, Today
from fitflow.api.schemas import AuthOut, LoginIn, RegisterIn
from fitflow.db.models import User
from fitflow.services import auth, tracking

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut, status_code=201)
def register(body: RegisterIn, db: DB, today: Today):
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(409, "Email already registered")

    fields = body.model_dump(exclude={"email", "password", "weight_kg"})
    user = tracking.create_user(
        db, today, **fields, email=email, password_hash=auth.hash_password(body.password),
        start_weight_kg=body.weight_kg,
    )
    return AuthOut(token=auth.create_token(user.id), user=user)


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, db: DB):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # One message for "no such email" and "wrong password": don't reveal which emails are registered.
    if user is None or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return AuthOut(token=auth.create_token(user.id), user=user)
