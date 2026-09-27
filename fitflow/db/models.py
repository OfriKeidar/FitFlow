"""Database tables (SQLAlchemy 2.0 ORM)."""

from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))  # never the password itself - see services/auth.py
    name: Mapped[str] = mapped_column(String(40))
    sex: Mapped[str] = mapped_column(String(10))
    age: Mapped[int]
    height_cm: Mapped[float]
    start_weight_kg: Mapped[float]
    activity: Mapped[str] = mapped_column(String(20))
    goal: Mapped[str] = mapped_column(String(20))
    target_weight_kg: Mapped[float | None] = mapped_column(default=None)
    pace: Mapped[str] = mapped_column(String(20), default="recommended")
    weigh_in_frequency: Mapped[str] = mapped_column(String(10), default="weekly")
    weekly_workout_goal: Mapped[int] = mapped_column(default=3)

    # The current TDEE estimate. Starts from the formula, then learned from data.
    tdee: Mapped[float]
    tdee_updated_on: Mapped[date]
    # The estimate before the last update that actually changed it (None if the last check
    # didn't have enough data). Lets every request that day report the same update.
    tdee_previous: Mapped[float | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    pantry: Mapped[list["PantryItem"]] = relationship(cascade="all, delete-orphan")
    disliked: Mapped[list["DislikedFood"]] = relationship(cascade="all, delete-orphan")


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    serving: Mapped[str] = mapped_column(String(50))
    kcal: Mapped[float]
    protein_g: Mapped[float]
    carbs_g: Mapped[float]
    fat_g: Mapped[float]
    category: Mapped[str] = mapped_column(String(20))
    meals: Mapped[str] = mapped_column(String(50))  # comma separated, e.g. "LUNCH,DINNER"


class FoodLogEntry(Base):
    """One thing the user ate.

    Nutrition values are COPIED from the food at logging time (a snapshot), so fixing a
    food's values later doesn't silently rewrite the user's history.
    """
    __tablename__ = "food_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(index=True)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id"))
    description: Mapped[str] = mapped_column(String(200))
    servings: Mapped[float]
    kcal: Mapped[float]
    protein_g: Mapped[float]
    carbs_g: Mapped[float]
    fat_g: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class WorkoutEntry(Base):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(index=True)
    activity: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(20))
    minutes: Mapped[float]
    kcal: Mapped[float]
    # Where it came from: "manual" (the app / chat) or "health_connect" (synced from the phone).
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    # The workout's id in the source app. Unique per user, so syncing twice never logs it twice.
    external_id: Mapped[str | None] = mapped_column(String(200), default=None)


class WeighInEntry(Base):
    __tablename__ = "weigh_ins"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date]
    weight_kg: Mapped[float]


class PantryItem(Base):
    __tablename__ = "pantry"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), primary_key=True)
    max_servings: Mapped[int]

    food: Mapped[Food] = relationship(lazy="joined")


class DislikedFood(Base):
    __tablename__ = "disliked_foods"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), primary_key=True)

    food: Mapped[Food] = relationship(lazy="joined")


class ChatMessage(Base):
    """One message in the coach conversation, stored exactly as sent to / received from the LLM.

    `content` is the whole message as JSON, in the provider's own format (tool calls and results
    look different in each API). We must replay messages unchanged on the next request, so we store
    them verbatim instead of only the visible text.
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(index=True)  # one conversation per day
    provider: Mapped[str] = mapped_column(String(30))  # which LLM API wrote it - see ai/providers.py
    role: Mapped[str] = mapped_column(String(10))  # "user" | "assistant" | "tool"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PendingAction(Base):
    """Something the AI wants to write (food, workout, weight) - saved only after the user confirms.

    This is the human-in-the-loop gate: the LLM can propose, but only a user click writes data.
    """
    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date]
    kind: Mapped[str] = mapped_column(String(20))    # "food" | "custom_food" | "workout" | "weight"
    payload: Mapped[str] = mapped_column(Text)       # validated JSON input for the action
    summary: Mapped[str] = mapped_column(Text)       # human-readable preview shown in the app
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | confirmed | rejected
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
