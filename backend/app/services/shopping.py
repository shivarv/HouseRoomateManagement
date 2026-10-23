"""The house's shared shopping list: anyone adds what's running out, anyone marks it bought.

- No duplicates: a name already on the list (any capitalisation) returns the existing item.
  A partial unique index backs this up when two people add the same thing at the same moment.
- The first person to mark an item bought wins: rows are locked, and later clicks are told who
  already bought it instead of overwriting them.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import HouseholdMember, ShoppingItem
from app.schemas.household import MemberBrief
from app.schemas.shopping import ShoppingItemOut, ShoppingList
from app.services import activity, grocery_settings
from app.services.errors import BadRequest, Conflict, Forbidden, NotFound

RECENT_DAYS = 14  # bought items stay visible this long

# Keyword → category, so "Head & Shoulders shampoo" lands in toiletries on every client.
_CATEGORY_WORDS = {
    "toiletries": (
        "shampoo",
        "conditioner",
        "soap bar",
        "body wash",
        "toothpaste",
        "toothbrush",
        "floss",
        "deodorant",
        "razor",
        "lotion",
        "hand wash",
        "handwash",
        "face wash",
        "sanitary",
        "pads",
        "tampon",
        "cotton",
    ),
    "cleaning": (
        "detergent",
        "washing",
        "dish",
        "bleach",
        "cleaner",
        "garbage",
        "trash",
        "bin bag",
        "sponge",
        "scrub",
        "mop",
        "disinfect",
        "lysol",
        "vim",
        "harpic",
    ),
    "household": (
        "tissue",
        "toilet paper",
        "toilet roll",
        "paper towel",
        "napkin",
        "foil",
        "cling",
        "battery",
        "batteries",
        "bulb",
        "candle",
        "match",
        "lighter",
        "ziploc",
        "bag",
    ),
    "groceries": (
        "egg",
        "milk",
        "rice",
        "oil",
        "bread",
        "flour",
        "atta",
        "sugar",
        "salt",
        "dal",
        "lentil",
        "onion",
        "tomato",
        "potato",
        "garlic",
        "ginger",
        "chilli",
        "chili",
        "butter",
        "ghee",
        "curd",
        "yogurt",
        "yoghurt",
        "cheese",
        "paneer",
        "chicken",
        "meat",
        "fish",
        "fruit",
        "banana",
        "apple",
        "vegetable",
        "spice",
        "masala",
        "tea",
        "coffee",
        "juice",
        "water",
        "cereal",
        "pasta",
        "noodle",
        "sauce",
        "ketchup",
        "jam",
        "honey",
    ),
}


def guess_category(name: str) -> str:
    """Keyword guess among the standard categories; "other" when nothing matches."""
    lowered = name.lower()
    for category, words in _CATEGORY_WORDS.items():
        if any(word in lowered for word in words):
            return category
    return "other"


def resolve_category(db: Session, household_id: uuid.UUID, name: str, requested: str | None) -> str:
    """The category asked for (it must exist in the house), else the quick-add item's, else a guess."""
    keys = grocery_settings.category_keys(db, household_id)
    if requested:
        if requested not in keys:
            raise BadRequest("That category doesn't exist in this house")
        return requested
    preset = grocery_settings.preset_named(db, household_id, name)
    if preset is not None and preset.status == "active" and preset.category_key in keys:
        return preset.category_key
    guess = guess_category(name)
    return guess if guess in keys else grocery_settings.FALLBACK


def get(db: Session, item_id: uuid.UUID) -> ShoppingItem:
    item = db.get(ShoppingItem, item_id)
    if item is None:
        raise NotFound("Item not found")
    return item


def _needed_named(db: Session, household_id: uuid.UUID, name: str) -> ShoppingItem | None:
    return db.scalar(
        select(ShoppingItem).where(
            ShoppingItem.household_id == household_id,
            ShoppingItem.status == "needed",
            func.lower(ShoppingItem.name) == name.lower(),
        )
    )


def _lock(db: Session, item_ids: list[uuid.UUID]) -> list[ShoppingItem]:
    # Lock the rows (in a fixed order, so two shoppers can't deadlock), then reload them so we
    # see whatever a click before ours committed. The eager joins can't be locked themselves.
    ids = list(dict.fromkeys(item_ids))  # as picked, without repeats
    db.execute(
        select(ShoppingItem.id)
        .where(ShoppingItem.id.in_(ids))
        .order_by(ShoppingItem.id)
        .with_for_update()
    )
    items = [db.get(ShoppingItem, i, populate_existing=True) for i in ids]
    return [i for i in items if i is not None]


def add(
    db: Session,
    me: HouseholdMember,
    name: str,
    quantity: str | None,
    category: str | None,
    note: str | None,
) -> tuple[ShoppingItem, bool]:
    """Returns (item, created). Already on the list → the existing item, unchanged."""
    existing = _needed_named(db, me.household_id, name)
    if existing is not None:
        return existing, False
    item = ShoppingItem(
        household_id=me.household_id,
        name=name,
        quantity=quantity or None,
        category=resolve_category(db, me.household_id, name, category),
        note=note or None,
        status="needed",
        added_by_id=me.id,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:  # someone added the same thing a moment ago
        db.rollback()
        existing = _needed_named(db, me.household_id, name)
        if existing is None:
            raise
        return existing, False
    activity.record(db, me.household_id, "shopping_added", me, detail=name)
    db.commit()
    db.refresh(item)
    return item, True


def update(
    db: Session,
    item_id: uuid.UUID,
    me: HouseholdMember,
    *,
    name: str | None,
    quantity: str | None,
    category: str | None,
    note: str | None,
) -> ShoppingItem:
    [item] = _lock(db, [item_id])
    if item.status == "bought":
        raise Conflict(f"{_name(item.bought_by)} already bought it, so it can't be edited")
    if name is not None and name.lower() != item.name.lower():
        if _needed_named(db, item.household_id, name) is not None:
            raise Conflict(f"{name} is already on the list")
    if name is not None:
        item.name = name
    if quantity is not None:
        item.quantity = quantity or None
    if category is not None:
        item.category = resolve_category(db, item.household_id, item.name, category)
    if note is not None:
        item.note = note or None
    db.commit()
    db.refresh(item)
    return item


def mark_bought(
    db: Session, item_ids: list[uuid.UUID], me: HouseholdMember, *, single: bool = False
) -> list[ShoppingItem]:
    """Mark items bought by me. Items someone else already bought keep their buyer.

    With `single`, losing that race is a 409 ("Bea already bought it") instead.
    """
    items = _lock(db, item_ids)
    if len(items) != len(set(item_ids)) or any(i.household_id != me.household_id for i in items):
        raise NotFound("Item not found")
    if single and items[0].status == "bought" and items[0].bought_by_id != me.id:
        raise Conflict(f"{_name(items[0].bought_by)} already bought it")

    now = datetime.now(UTC)
    newly = [i for i in items if i.status == "needed"]
    for item in newly:
        item.status = "bought"
        item.bought_by_id = me.id
        item.bought_at = now
    if newly:
        activity.record(
            db,
            me.household_id,
            "shopping_bought",
            me,
            detail=", ".join(i.name for i in newly)[:200],
        )
    db.commit()
    for item in items:
        db.refresh(item)
    return items


def undo(db: Session, item_id: uuid.UUID, me: HouseholdMember) -> ShoppingItem:
    """Back on the list: whoever bought it, or whoever added it."""
    [item] = _lock(db, [item_id])
    if item.status == "needed":
        return item
    if me.id not in (item.bought_by_id, item.added_by_id):
        raise Forbidden("Only the person who bought it or added it can undo this")
    if _needed_named(db, item.household_id, item.name) is not None:
        raise Conflict(f"{item.name} is already back on the list")
    previous = item.bought_by_id
    item.status = "needed"
    item.bought_by_id = None
    item.bought_at = None
    activity.record(
        db, item.household_id, "shopping_unbought", me, subject_id=previous, detail=item.name
    )
    db.commit()
    db.refresh(item)
    return item


def remove(db: Session, item_id: uuid.UUID, me: HouseholdMember) -> None:
    """Anyone can take a still-needed item off the list (e.g. there's some left after all)."""
    [item] = _lock(db, [item_id])
    if item.status == "bought":
        raise BadRequest("Bought items stay in the history; use Undo instead")
    activity.record(db, item.household_id, "shopping_removed", me, detail=item.name)
    db.delete(item)
    db.commit()


def shopping_list(db: Session, me: HouseholdMember) -> ShoppingList:
    now = datetime.now(UTC)
    needed = list(
        db.scalars(
            select(ShoppingItem)
            .where(ShoppingItem.household_id == me.household_id, ShoppingItem.status == "needed")
            .order_by(ShoppingItem.created_at)
        ).unique()
    )
    bought = list(
        db.scalars(
            select(ShoppingItem)
            .where(
                ShoppingItem.household_id == me.household_id,
                ShoppingItem.status == "bought",
                ShoppingItem.bought_at >= now - timedelta(days=RECENT_DAYS),
            )
            .order_by(ShoppingItem.bought_at.desc())
        ).unique()
    )
    return ShoppingList(
        needed=[out(i, me) for i in needed],
        recently_bought=[out(i, me) for i in bought],
        categories=[
            grocery_settings.category_out(c)
            for c in grocery_settings.categories(db, me.household_id)
        ],
        quick_add=[
            grocery_settings.preset_out(p) for p in grocery_settings.presets(db, me.household_id)
        ],
    )


def _name(member: HouseholdMember | None) -> str:
    return member.display_name if member else "Someone"


def _brief(member: HouseholdMember | None) -> MemberBrief | None:
    return MemberBrief(id=member.id, display_name=member.display_name) if member else None


def out(item: ShoppingItem, me: HouseholdMember) -> ShoppingItemOut:
    return ShoppingItemOut(
        id=item.id,
        name=item.name,
        quantity=item.quantity,
        category=item.category,
        note=item.note,
        status=item.status,
        added_by=_brief(item.added_by),
        bought_by=_brief(item.bought_by),
        bought_at=item.bought_at,
        created_at=item.created_at,
        can_undo=item.status == "bought" and me.id in (item.bought_by_id, item.added_by_id),
    )
