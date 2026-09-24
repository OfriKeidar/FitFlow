from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from fitflow.api.deps import DB, CurrentUser
from fitflow.api.schemas import FoodOut, PantryItemIn, PantryItemOut
from fitflow.db.models import DislikedFood, Food, PantryItem

router = APIRouter(tags=["foods"])


def _food_or_404(db: DB, food_id: int) -> Food:
    food = db.get(Food, food_id)
    if food is None:
        raise HTTPException(404, "Food not found")
    return food


@router.get("/foods", response_model=list[FoodOut])
def search_foods(db: DB, q: str = "", limit: int = 20):
    query = select(Food).order_by(Food.name).limit(limit)
    if q:
        query = query.where(Food.name.contains(q))
    return db.scalars(query).all()


@router.get("/pantry", response_model=list[PantryItemOut])
def get_pantry(user: CurrentUser):
    return user.pantry


@router.put("/pantry/{food_id}", response_model=PantryItemOut)
def set_pantry_item(food_id: int, body: PantryItemIn, user: CurrentUser, db: DB):
    _food_or_404(db, food_id)
    item = db.get(PantryItem, (user.id, food_id))
    if item is None:
        item = PantryItem(user_id=user.id, food_id=food_id, max_servings=body.max_servings)
        db.add(item)
    else:
        item.max_servings = body.max_servings
    db.commit()
    db.refresh(item)
    return item


@router.delete("/pantry/{food_id}", status_code=204)
def remove_pantry_item(food_id: int, user: CurrentUser, db: DB):
    item = db.get(PantryItem, (user.id, food_id))
    if item is not None:
        db.delete(item)
        db.commit()


@router.get("/disliked", response_model=list[FoodOut])
def get_disliked(user: CurrentUser):
    return [d.food for d in user.disliked]


@router.put("/disliked/{food_id}", status_code=204)
def add_disliked(food_id: int, user: CurrentUser, db: DB):
    _food_or_404(db, food_id)
    if db.get(DislikedFood, (user.id, food_id)) is None:
        db.add(DislikedFood(user_id=user.id, food_id=food_id))
        db.commit()


@router.delete("/disliked/{food_id}", status_code=204)
def remove_disliked(food_id: int, user: CurrentUser, db: DB):
    item = db.get(DislikedFood, (user.id, food_id))
    if item is not None:
        db.delete(item)
        db.commit()
