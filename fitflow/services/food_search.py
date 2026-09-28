"""Food search with relevance ranking - used by the app's search box and by the AI coach.

With ~13,000 foods, a plain "name contains" search returns the wrong thing first: for "ביצה",
the shortest match is dried egg powder (605 kcal per 100 g). So results are ranked:

    0. names containing every word of the query first ("חומוס צבר" -> the Tzabar product)
    1. our common foods first (fresh egg, chicken breast...) - the usual intent
    2. how well the name matches: exact > starts with the query > contains it as a word > contains it
    3. processed forms (dried, powder, flour, infant formula...) last, unless the user asked for them
    4. generic foods (national database) before branded products (Open Food Facts) - unless the
       product matches better, e.g. searching a brand name
    5. shorter (simpler) names first
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from fitflow.db.models import Food

# Words that mark a processed / special form that is rarely what someone means by the plain food.
PROCESSED = ("מיובש", "אבקה", "אבקת", "קמח", "תמ\"ל", "תרכיז", "לתינוקות", "מזון תינוקות", "מוקפא יבש", "משומר")
CANDIDATES = 300  # rank in Python among at most this many database matches
SOURCE_ORDER = {"fitflow": 0, "tzameret": 1, "off": 2}


def match_score(name: str, query: str) -> int:
    """Lower is better."""
    if name == query:
        return 0
    if name.startswith(query + ",") or name.startswith(query + " ") or name.startswith(query):
        return 1
    if f" {query} " in f" {name.replace(',', ' ')} ":
        return 2  # a whole word inside the name
    if query in name:
        return 3
    return 4  # matched only some of the words


def missing_words(name: str, query: str) -> int:
    return sum(word not in name for word in query.split())


def rank_key(food: Food, query: str) -> tuple:
    processed = any(word in food.name for word in PROCESSED) and not any(word in query for word in PROCESSED)
    source = SOURCE_ORDER.get(food.source, 3)
    return (missing_words(food.name, query), source != 0, match_score(food.name, query), processed, source,
            len(food.name), food.name)


def search_foods(session: Session, query: str, limit: int = 20, with_units: bool = False) -> list[Food]:
    query = " ".join(query.split())
    if not query:
        return list(session.scalars(select(Food).where(Food.source == "fitflow").order_by(Food.name).limit(limit)))

    words = query.split()
    statement = select(Food).where(or_(Food.name.contains(query), *(Food.name.contains(w) for w in words)))
    if with_units:
        statement = statement.options(selectinload(Food.units))  # one extra query, not one per food
    # Common words ("חלב") match thousands of names. Keep the shortest ones: an unordered LIMIT
    # could drop the exact match. Then rank those precisely in Python.
    statement = statement.order_by(Food.source != "fitflow", func.length(Food.name)).limit(CANDIDATES)
    candidates = session.scalars(statement).all()
    return sorted(candidates, key=lambda food: rank_key(food, query))[:limit]
