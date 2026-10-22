import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models import HouseholdMember
from app.schemas.shopping import (
    ShoppingBought,
    ShoppingItemCreate,
    ShoppingItemOut,
    ShoppingItemUpdate,
    ShoppingList,
)
from app.services import households as household_svc
from app.services import shopping as shopping_svc

router = APIRouter(tags=["shopping list"])


@router.get("/households/{household_id}/shopping", response_model=ShoppingList)
def get_shopping_list(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """What the house needs, what was bought in the last two weeks, and quick-add suggestions."""
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
