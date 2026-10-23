import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models import HouseholdMember
from app.schemas.shopping import (
    GroceryCategoryCreate,
    GroceryCategoryOut,
    GroceryCategoryUpdate,
    GroceryOrder,
    GroceryPresetCreate,
    GroceryPresetOut,
    GroceryPresetUpdate,
    GrocerySettings,
    GrocerySuggestionDismiss,
    ShoppingBought,
    ShoppingItemCreate,
    ShoppingItemOut,
    ShoppingItemUpdate,
    ShoppingList,
)
from app.services import grocery_settings as settings_svc
from app.services import households as household_svc
from app.services import shopping as shopping_svc

router = APIRouter(tags=["shopping list"])


@router.get("/households/{household_id}/shopping", response_model=ShoppingList)
def get_shopping_list(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """What the house needs, what was bought in the last two weeks, its categories and quick-add items."""
    me = household_svc.require_membership(db, household_id, user)
    return shopping_svc.shopping_list(db, me)


@router.post(
    "/households/{household_id}/shopping",
    response_model=ShoppingItemOut,
    status_code=status.HTTP_201_CREATED,
)
def add_item(
    household_id: uuid.UUID,
    body: ShoppingItemCreate,
    db: DbSession,
    user: CurrentUser,
    response: Response,
):
    """Already on the list (any capitalisation)? Returns that item with 200 instead of a copy."""
    me = household_svc.require_membership(db, household_id, user)
    item, created = shopping_svc.add(db, me, body.name, body.quantity, body.category, body.note)
    if not created:
        response.status_code = status.HTTP_200_OK
    return shopping_svc.out(item, me)


@router.post("/households/{household_id}/shopping/bought", response_model=list[ShoppingItemOut])
def mark_many_bought(
    household_id: uuid.UUID, body: ShoppingBought, db: DbSession, user: CurrentUser
):
    """One shopping trip. Items someone else already bought keep their buyer."""
    me = household_svc.require_membership(db, household_id, user)
    return [shopping_svc.out(i, me) for i in shopping_svc.mark_bought(db, body.item_ids, me)]


def _me(db, item_id: uuid.UUID, user) -> tuple[uuid.UUID, HouseholdMember]:
    """The item's id, and the caller's membership in its household (404 if not a member)."""
    item = shopping_svc.get(db, item_id)
    return item.id, household_svc.require_membership(db, item.household_id, user)


@router.patch("/shopping/{item_id}", response_model=ShoppingItemOut)
def edit_item(item_id: uuid.UUID, body: ShoppingItemUpdate, db: DbSession, user: CurrentUser):
    iid, me = _me(db, item_id, user)
    item = shopping_svc.update(
        db,
        iid,
        me,
        name=body.name,
        quantity=body.quantity,
        category=body.category,
        note=body.note,
    )
    return shopping_svc.out(item, me)


@router.post("/shopping/{item_id}/bought", response_model=ShoppingItemOut)
def mark_bought(item_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """The first person wins; anyone after gets 409 "Bea already bought it"."""
    iid, me = _me(db, item_id, user)
    [item] = shopping_svc.mark_bought(db, [iid], me, single=True)
    return shopping_svc.out(item, me)


@router.post("/shopping/{item_id}/undo", response_model=ShoppingItemOut)
def undo_bought(item_id: uuid.UUID, db: DbSession, user: CurrentUser):
    iid, me = _me(db, item_id, user)
    return shopping_svc.out(shopping_svc.undo(db, iid, me), me)


@router.delete("/shopping/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(item_id: uuid.UUID, db: DbSession, user: CurrentUser):
    iid, me = _me(db, item_id, user)
    shopping_svc.remove(db, iid, me)


# --- Admin: the house's grocery set-up ---------------------------------------------------------


@router.get("/households/{household_id}/grocery-settings", response_model=GrocerySettings)
def get_grocery_settings(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Categories, quick-add items, and what people added that isn't a quick-add item yet."""
    household_svc.require_membership(db, household_id, user, admin=True)
    return settings_svc.settings(db, household_id)


@router.post("/households/{household_id}/grocery-settings/restore", response_model=GrocerySettings)
def restore_standard(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Bring back removed standard categories and quick-add items. Nothing custom is touched."""
    household_svc.require_membership(db, household_id, user, admin=True)
    return settings_svc.restore_standard(db, household_id)


@router.post(
    "/households/{household_id}/grocery-categories",
    response_model=GroceryCategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def add_category(
    household_id: uuid.UUID, body: GroceryCategoryCreate, db: DbSession, user: CurrentUser
):
    household_svc.require_membership(db, household_id, user, admin=True)
    return settings_svc.category_out(
        settings_svc.add_category(db, household_id, body.label, body.icon)
    )


@router.put("/households/{household_id}/grocery-categories/order", status_code=204)
def reorder_categories(household_id: uuid.UUID, body: GroceryOrder, db: DbSession, user: CurrentUser):
    household_svc.require_membership(db, household_id, user, admin=True)
    settings_svc.reorder_categories(db, household_id, body.ids)


@router.patch("/grocery-categories/{category_id}", response_model=GroceryCategoryOut)
def edit_category(
    category_id: uuid.UUID, body: GroceryCategoryUpdate, db: DbSession, user: CurrentUser
):
    category = settings_svc.get_category(db, category_id)
    household_svc.require_membership(db, category.household_id, user, admin=True)
    return settings_svc.category_out(
        settings_svc.update_category(db, category, body.label, body.icon)
    )


@router.delete("/grocery-categories/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Its items and quick-add items move to "Other"."""
    category = settings_svc.get_category(db, category_id)
    household_svc.require_membership(db, category.household_id, user, admin=True)
    settings_svc.delete_category(db, category)


@router.post(
    "/households/{household_id}/grocery-presets",
    response_model=GroceryPresetOut,
    status_code=status.HTTP_201_CREATED,
)
def add_preset(household_id: uuid.UUID, body: GroceryPresetCreate, db: DbSession, user: CurrentUser):
    """Also how a suggestion is accepted. Without a category, it's guessed from the name."""
    household_svc.require_membership(db, household_id, user, admin=True)
    key = shopping_svc.resolve_category(db, household_id, body.name, body.category_key)
    return settings_svc.preset_out(settings_svc.add_preset(db, household_id, body.name, key))


@router.post("/households/{household_id}/grocery-suggestions/dismiss", status_code=204)
def dismiss_suggestion(
    household_id: uuid.UUID, body: GrocerySuggestionDismiss, db: DbSession, user: CurrentUser
):
    """Stop suggesting this name. Adding it as a quick-add item later still works."""
    household_svc.require_membership(db, household_id, user, admin=True)
    guess = shopping_svc.resolve_category(db, household_id, body.name, None)
    settings_svc.dismiss_suggestion(db, household_id, body.name, guess)


@router.patch("/grocery-presets/{preset_id}", response_model=GroceryPresetOut)
def edit_preset(preset_id: uuid.UUID, body: GroceryPresetUpdate, db: DbSession, user: CurrentUser):
    preset = settings_svc.get_preset(db, preset_id)
    household_svc.require_membership(db, preset.household_id, user, admin=True)
    return settings_svc.preset_out(
        settings_svc.update_preset(db, preset, body.name, body.category_key)
    )


@router.delete("/grocery-presets/{preset_id}", status_code=204)
def remove_preset(preset_id: uuid.UUID, db: DbSession, user: CurrentUser):
    preset = settings_svc.get_preset(db, preset_id)
    household_svc.require_membership(db, preset.household_id, user, admin=True)
    settings_svc.remove_preset(db, preset)
