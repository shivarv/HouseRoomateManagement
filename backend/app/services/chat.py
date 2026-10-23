"""A house's group chat. Clients poll for new messages (`after`) and page back (`before`)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatRead, HouseholdMember
from app.schemas.chat import ChatMessageOut, ChatPage
from app.schemas.household import MemberBrief
from app.services.errors import BadRequest, Forbidden, NotFound

PAGE = 50


def page(
    db: Session,
    me: HouseholdMember,
    before: datetime | None = None,
    after: datetime | None = None,
    limit: int = PAGE,
) -> ChatPage:
    """`after`: messages newer than that (polling), oldest first. Otherwise the latest `limit`
    before `before` (or now). Messages edited or deleted since `after` come back too."""
    query = select(ChatMessage).where(ChatMessage.household_id == me.household_id)
    if after is not None:
        changed = func.greatest(
            ChatMessage.created_at,
            func.coalesce(ChatMessage.edited_at, ChatMessage.created_at),
            func.coalesce(ChatMessage.deleted_at, ChatMessage.created_at),
        )
        rows = list(db.scalars(query.where(changed > after).order_by(ChatMessage.created_at).limit(200)).unique())
        return ChatPage(messages=[out(m, me) for m in rows], has_more=False)
    if before is not None:
        query = query.where(ChatMessage.created_at < before)
    rows = list(db.scalars(query.order_by(ChatMessage.created_at.desc()).limit(limit + 1)).unique())
    more = len(rows) > limit
    return ChatPage(messages=[out(m, me) for m in reversed(rows[:limit])], has_more=more)


def send(db: Session, me: HouseholdMember, body: str) -> ChatMessage:
    if not body.strip():
        raise BadRequest("Write something first")
    message = ChatMessage(household_id=me.household_id, author_id=me.id, body=body)
    db.add(message)
    db.flush()
    mark_read(db, me, commit=False)  # my own message isn't unread for me
    db.commit()
    db.refresh(message)
    return message


def get(db: Session, message_id: uuid.UUID) -> ChatMessage:
    message = db.get(ChatMessage, message_id)
    if message is None:
        raise NotFound("Message not found")
    return message


def edit(db: Session, message: ChatMessage, me: HouseholdMember, body: str) -> ChatMessage:
    if message.author_id != me.id:
        raise Forbidden("You can only edit your own messages")
    if message.deleted_at is not None:
        raise BadRequest("This message was deleted")
    message.body = body
    message.edited_at = func.now()  # the database's clock, like created_at, so polling compares fairly
    db.commit()
    db.refresh(message)
    return message


def delete(db: Session, message: ChatMessage, me: HouseholdMember) -> ChatMessage:
    if message.author_id != me.id and me.role != "admin":
        raise Forbidden("Only whoever wrote it or an admin can delete a message")
    message.deleted_at = func.now()
    message.body = ""
    db.commit()
    db.refresh(message)
    return message


def mark_read(db: Session, me: HouseholdMember, commit: bool = True) -> None:
    # The database's clock, the same one message times come from.
    db.execute(
        insert(ChatRead)
        .values(member_id=me.id, last_read_at=func.now())
        .on_conflict_do_update(index_elements=["member_id"], set_={"last_read_at": func.now()})
    )
    if commit:
        db.commit()


def unread(db: Session, me: HouseholdMember) -> int:
    """Others' messages since I last read the chat (all of them if I never opened it)."""
    last = db.scalar(select(ChatRead.last_read_at).where(ChatRead.member_id == me.id))
    query = select(func.count()).where(
        ChatMessage.household_id == me.household_id,
        ChatMessage.deleted_at.is_(None),
        (ChatMessage.author_id != me.id) | ChatMessage.author_id.is_(None),
    )
    if last is not None:
        query = query.where(ChatMessage.created_at > last)
    return db.scalar(query) or 0


def out(message: ChatMessage, me: HouseholdMember) -> ChatMessageOut:
    author = message.author
    deleted = message.deleted_at is not None
    mine = message.author_id == me.id
    return ChatMessageOut(
        id=message.id,
        author=MemberBrief(id=author.id, display_name=author.display_name) if author else None,
        body="" if deleted else message.body,
        created_at=message.created_at,
        edited_at=message.edited_at,
        changed_at=max(t for t in (message.created_at, message.edited_at, message.deleted_at) if t),
        deleted=deleted,
        is_mine=mine,
        can_edit=mine and not deleted,
        can_delete=not deleted and (mine or me.role == "admin"),
    )
