import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.household import MemberBrief


def _clean(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value  # keep line breaks inside


class ChatSend(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    _strip = field_validator("body", mode="before")(_clean)


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    author: MemberBrief | None  # None if they left the house
    body: str  # "" once deleted
    created_at: datetime
    edited_at: datetime | None
    changed_at: datetime  # sent, edited or deleted, whichever is latest: poll with after=<newest>
    deleted: bool
    is_mine: bool
    can_edit: bool  # mine and not deleted
    can_delete: bool  # mine, or I'm an admin


class ChatPage(BaseModel):
    messages: list[ChatMessageOut]  # oldest first
    has_more: bool  # older messages exist (ask again with before=<oldest created_at>)


class ChatUnread(BaseModel):
    count: int
