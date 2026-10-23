import uuid
from datetime import datetime

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.chat import ChatMessageOut, ChatPage, ChatSend, ChatUnread
from app.services import chat as svc
from app.services import households as household_svc

router = APIRouter(tags=["chat"])


@router.get("/households/{household_id}/chat", response_model=ChatPage)
def list_messages(
    household_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    before: datetime | None = None,
    after: datetime | None = None,
    limit: int = Query(svc.PAGE, ge=1, le=100),
):
    """Latest messages (oldest first). `before`: page back. `after`: what's new or changed since then."""
    me = household_svc.require_membership(db, household_id, user)
    return svc.page(db, me, before=before, after=after, limit=limit)


@router.post(
    "/households/{household_id}/chat",
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(household_id: uuid.UUID, body: ChatSend, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user)
    return svc.out(svc.send(db, me, body.body), me)


@router.post("/households/{household_id}/chat/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user)
    svc.mark_read(db, me)


@router.get("/households/{household_id}/chat/unread", response_model=ChatUnread)
def unread(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user)
    return ChatUnread(count=svc.unread(db, me))


def _me(db, message_id: uuid.UUID, user):
    message = svc.get(db, message_id)
    return message, household_svc.require_membership(db, message.household_id, user)


@router.patch("/chat-messages/{message_id}", response_model=ChatMessageOut)
def edit_message(message_id: uuid.UUID, body: ChatSend, db: DbSession, user: CurrentUser):
    message, me = _me(db, message_id, user)
    return svc.out(svc.edit(db, message, me, body.body), me)


@router.delete("/chat-messages/{message_id}", response_model=ChatMessageOut)
def delete_message(message_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Whoever wrote it, or an admin. It stays in the list as "Message deleted"."""
    message, me = _me(db, message_id, user)
    return svc.out(svc.delete(db, message, me), me)
