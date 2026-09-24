from fastapi import APIRouter

from fitflow.api.deps import DB, CurrentUser, Today
from fitflow.api.schemas import UserCreate, UserOut, UserUpdate
from fitflow.services import tracking

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DB, today: Today):
    fields = body.model_dump()
    fields["start_weight_kg"] = fields.pop("weight_kg")
    return tracking.create_user(db, today, **fields)


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: CurrentUser, db: DB):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    return user
