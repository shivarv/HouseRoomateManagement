"""The house's grocery set-up: list sections (categories) and quick-add items. Admins edit both.

Every house starts with the standard lists below and can change them freely. Items people add
that aren't quick-add items yet show up as suggestions for the admin, who adds or dismisses them.
Removing a quick-add item only dismisses it, so it doesn't come straight back as a suggestion.
"""

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import GroceryCategory, GroceryPreset, ShoppingItem
from app.schemas.shopping import (
    GroceryCategoryOut,
    GroceryPresetOut,
    GrocerySettings,
    GrocerySuggestion,
)
from app.services.errors import BadRequest, Conflict, NotFound

FALLBACK = "other"
SUGGESTION_DAYS = 120
MAX_SUGGESTIONS = 20

# (key, label, icon). Keys are what shopping items store; labels and icons can be renamed.
STANDARD_CATEGORIES = (
    ("groceries", "Groceries", "🛒"),
    ("toiletries", "Toiletries", "🧴"),
    ("cleaning", "Cleaning", "🧼"),
    ("household", "Household", "🧻"),
    (FALLBACK, "Other", "🛍️"),
)

STANDARD_PRESETS = (
    ("Eggs", "groceries"),
    ("Milk", "groceries"),
    ("Rice", "groceries"),
    ("Oil", "groceries"),
    ("Bread", "groceries"),
    ("Onions", "groceries"),
    ("Shampoo", "toiletries"),
    ("Toothpaste", "toiletries"),
    ("Hand wash", "toiletries"),
    ("Washing soap", "cleaning"),
    ("Dish soap", "cleaning"),
    ("Garbage bags", "cleaning"),
    ("Tissues", "household"),
    ("Toilet paper", "household"),
    ("Paper towels", "household"),
)


# --- Reading ----------------------------------------------------------------------------------


def categories(db: Session, household_id: uuid.UUID) -> list[GroceryCategory]:
    return list(
        db.scalars(
            select(GroceryCategory)
            .where(GroceryCategory.household_id == household_id)
            .order_by(GroceryCategory.position, GroceryCategory.created_at)
        )
    )


def category_keys(db: Session, household_id: uuid.UUID) -> set[str]:
    return set(
        db.scalars(select(GroceryCategory.key).where(GroceryCategory.household_id == household_id))
    )


def presets(db: Session, household_id: uuid.UUID) -> list[GroceryPreset]:
    return list(
        db.scalars(
            select(GroceryPreset)
            .where(GroceryPreset.household_id == household_id, GroceryPreset.status == "active")
            .order_by(func.lower(GroceryPreset.name))  # alphabetical; clients group them by type
        )
    )


def preset_named(db: Session, household_id: uuid.UUID, name: str) -> GroceryPreset | None:
    """Any preset with this name (any capitalisation), active or dismissed."""
    return db.scalar(
        select(GroceryPreset).where(
            GroceryPreset.household_id == household_id,
            func.lower(GroceryPreset.name) == name.lower(),
        )
    )


def suggestions(db: Session, household_id: uuid.UUID) -> list[GrocerySuggestion]:
    """Names added recently that the admin hasn't made quick-add items or dismissed."""
    since = datetime.now(UTC) - timedelta(days=SUGGESTION_DAYS)
    known = select(func.lower(GroceryPreset.name)).where(
        GroceryPreset.household_id == household_id
    )
    rows = db.execute(
        select(ShoppingItem.name, ShoppingItem.category)
        .where(
            ShoppingItem.household_id == household_id,
            ShoppingItem.created_at >= since,
            func.lower(ShoppingItem.name).not_in(known),
        )
        .order_by(ShoppingItem.created_at.desc())
    ).all()
    found: dict[str, GrocerySuggestion] = {}
    for name, category in rows:  # newest first: keep the latest spelling and category
        entry = found.get(name.lower())
        if entry is None:
            found[name.lower()] = GrocerySuggestion(name=name, times_added=1, category_key=category)
        else:
            entry.times_added += 1
    ranked = sorted(found.values(), key=lambda s: -s.times_added)  # stable: newest first on ties
    return ranked[:MAX_SUGGESTIONS]


def settings(db: Session, household_id: uuid.UUID) -> GrocerySettings:
    return GrocerySettings(
        categories=[category_out(c) for c in categories(db, household_id)],
        presets=[preset_out(p) for p in presets(db, household_id)],
        suggestions=suggestions(db, household_id),
    )


# --- Setting up a house -----------------------------------------------------------------------


def seed(db: Session, household_id: uuid.UUID) -> None:
    """Give a new house the standard categories and quick-add items. The caller commits."""
    for position, (key, label, icon) in enumerate(STANDARD_CATEGORIES):
        db.add(
            GroceryCategory(
                household_id=household_id, key=key, label=label, icon=icon, position=position
            )
        )
    for position, (name, key) in enumerate(STANDARD_PRESETS):
        db.add(
            GroceryPreset(
                household_id=household_id, name=name, category_key=key, position=position
            )
        )


def restore_standard(db: Session, household_id: uuid.UUID) -> GrocerySettings:
    """Bring back any standard category or quick-add item that was removed. Adds, never deletes."""
    keys = category_keys(db, household_id)
    labels = {c.label.lower() for c in categories(db, household_id)}
    next_cat = len(keys)
    for key, label, icon in STANDARD_CATEGORIES:
        if key in keys:
            continue
        if label.lower() in labels:  # a custom category took the name: keep it, skip ours
            continue
        db.add(
            GroceryCategory(
                household_id=household_id, key=key, label=label, icon=icon, position=next_cat
            )
        )
        keys.add(key)
        next_cat += 1
    db.flush()
    next_preset = _next_preset_position(db, household_id)
    for name, key in STANDARD_PRESETS:
        existing = preset_named(db, household_id, name)
        if existing is not None and existing.status == "active":
            continue
        category = key if key in keys else FALLBACK
        if existing is None:
            db.add(
                GroceryPreset(
                    household_id=household_id,
                    name=name,
                    category_key=category,
                    position=next_preset,
                )
            )
        else:
            existing.status = "active"
            existing.category_key = category
            existing.position = next_preset
        next_preset += 1
    db.commit()
    return settings(db, household_id)


# --- Categories -------------------------------------------------------------------------------


def get_category(db: Session, category_id: uuid.UUID) -> GroceryCategory:
    category = db.get(GroceryCategory, category_id)
    if category is None:
        raise NotFound("Category not found")
    return category


def _ensure_label_free(
    db: Session, household_id: uuid.UUID, label: str, exclude: uuid.UUID | None = None
) -> None:
    query = select(GroceryCategory.id).where(
        GroceryCategory.household_id == household_id,
        func.lower(GroceryCategory.label) == label.lower(),
    )
    if exclude is not None:
        query = query.where(GroceryCategory.id != exclude)
    if db.scalar(query) is not None:
        raise Conflict(f"There's already a category called “{label}”")


def _new_key(label: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:30] or "category"
    key = base
    while key in taken:
        key = f"{base}-{secrets.token_hex(2)}"
    return key


def add_category(db: Session, household_id: uuid.UUID, label: str, icon: str) -> GroceryCategory:
    _ensure_label_free(db, household_id, label)
    taken = category_keys(db, household_id)
    category = GroceryCategory(
        household_id=household_id,
        key=_new_key(label, taken),
        label=label,
        icon=icon,
        position=len(taken),
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session, category: GroceryCategory, label: str | None, icon: str | None
) -> GroceryCategory:
    if label is not None:
        _ensure_label_free(db, category.household_id, label, exclude=category.id)
        category.label = label
    if icon is not None:
        category.icon = icon
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category: GroceryCategory) -> None:
    """Items and quick-add items in it move to "Other", so nothing on the list disappears."""
    if category.key == FALLBACK:
        raise BadRequest("“Other” is where everything else goes, so it can't be deleted")
    db.execute(
        update(ShoppingItem)
        .where(
            ShoppingItem.household_id == category.household_id,
            ShoppingItem.category == category.key,
        )
        .values(category=FALLBACK)
    )
    db.execute(
        update(GroceryPreset)
        .where(
            GroceryPreset.household_id == category.household_id,
            GroceryPreset.category_key == category.key,
        )
        .values(category_key=FALLBACK)
    )
    db.delete(category)
    db.commit()


def reorder_categories(db: Session, household_id: uuid.UUID, ids: list[uuid.UUID]) -> None:
    by_id = {c.id: c for c in categories(db, household_id)}
    if len(ids) != len(set(ids)) or set(ids) != set(by_id):
        raise BadRequest("Send every category of the house exactly once, in the new order")
    for position, category_id in enumerate(ids):
        by_id[category_id].position = position
    db.commit()


# --- Quick-add items --------------------------------------------------------------------------


def get_preset(db: Session, preset_id: uuid.UUID) -> GroceryPreset:
    preset = db.get(GroceryPreset, preset_id)
    if preset is None or preset.status != "active":
        raise NotFound("Quick-add item not found")
    return preset


def require_category(db: Session, household_id: uuid.UUID, key: str) -> str:
    if key not in category_keys(db, household_id):
        raise BadRequest("That category doesn't exist in this house")
    return key


def _next_preset_position(db: Session, household_id: uuid.UUID) -> int:
    top = db.scalar(
        select(func.max(GroceryPreset.position)).where(
            GroceryPreset.household_id == household_id, GroceryPreset.status == "active"
        )
    )
    return 0 if top is None else top + 1


def add_preset(db: Session, household_id: uuid.UUID, name: str, category_key: str) -> GroceryPreset:
    """Also how a suggestion is accepted. A dismissed name comes back instead of a copy."""
    require_category(db, household_id, category_key)
    position = _next_preset_position(db, household_id)
    existing = preset_named(db, household_id, name)
    if existing is not None and existing.status == "active":
        raise Conflict(f"{existing.name} is already a quick-add item")
    if existing is None:
        existing = GroceryPreset(household_id=household_id, name=name)
        db.add(existing)
    existing.name = name
    existing.category_key = category_key
    existing.status = "active"
    existing.position = position
    db.commit()
    db.refresh(existing)
    return existing


def update_preset(
    db: Session, preset: GroceryPreset, name: str | None, category_key: str | None
) -> GroceryPreset:
    if name is not None and name.lower() != preset.name.lower():
        other = preset_named(db, preset.household_id, name)
        if other is not None and other.status == "active":
            raise Conflict(f"{other.name} is already a quick-add item")
        if other is not None:  # a dismissed row with that name: this one takes over
            db.delete(other)
            db.flush()
    if name is not None:
        preset.name = name
    if category_key is not None:
        preset.category_key = require_category(db, preset.household_id, category_key)
    db.commit()
    db.refresh(preset)
    return preset


def remove_preset(db: Session, preset: GroceryPreset) -> None:
    """Dismissed, not deleted: otherwise anything the house bought before would be suggested again."""
    preset.status = "dismissed"
    db.commit()


def dismiss_suggestion(db: Session, household_id: uuid.UUID, name: str, guess: str) -> None:
    existing = preset_named(db, household_id, name)
    if existing is not None:
        return  # already a quick-add item, or already dismissed
    db.add(GroceryPreset(household_id=household_id, name=name, category_key=guess, status="dismissed"))
    db.commit()


# --- Shared -----------------------------------------------------------------------------------


def category_out(category: GroceryCategory) -> GroceryCategoryOut:
    return GroceryCategoryOut(
        id=category.id,
        key=category.key,
        label=category.label,
        icon=category.icon,
        position=category.position,
        can_delete=category.key != FALLBACK,
    )


def preset_out(preset: GroceryPreset) -> GroceryPresetOut:
    return GroceryPresetOut(
        id=preset.id, name=preset.name, category_key=preset.category_key, position=preset.position
    )
