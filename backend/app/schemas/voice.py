import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import _clean

# What voice can do: the things Claude proposes, and their undos (run through the same endpoint, so
# Undo after a voice command works like the buttons do).
ActionType = Literal[
    "complete_task",  # a rotation turn, by me or someone else
    "reopen_task",
    "log_open_chore",  # an open chore anyone can do (e.g. garbage)
    "remove_log",
    "pay_bill",  # optionally with this period's amount
    "undo_payment",
    "add_groceries",
    "mark_bought",
    "unbuy",
    "remove_grocery",
    "send_chat",
    "delete_chat",
    "ask_favour",
    "favour_done",
    "reopen_favour",
    "withdraw_favour",
]


class VoiceAction(BaseModel):
    """One action, with real ids. Only the fields its `type` uses are set."""

    type: ActionType
    task_id: uuid.UUID | None = None
    chore_id: uuid.UUID | None = None
    log_id: uuid.UUID | None = None
    member_id: uuid.UUID | None = None  # who did it / paid; None = me
    bill_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    names: list[str] = Field(default=[], max_length=20)
    item_ids: list[uuid.UUID] = Field(default=[], max_length=50)
    message_id: uuid.UUID | None = None
    text: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=120)
    details: str | None = Field(default=None, max_length=500)
    request_id: uuid.UUID | None = None

    _strip = field_validator("text", "title", "details", mode="before")(_clean)


class VoiceProposal(BaseModel):
    """A card to confirm: what will happen, in words from our own data (not from Claude)."""

    action: VoiceAction
    summary: str  # "Take out trash · done by Raj"
    area: Literal["chores", "bills", "groceries", "chat", "favours"]


class VoiceFollowUp(BaseModel):
    """The answer to a question voice asked back ("Which bathroom?")."""

    question: str = Field(max_length=300)
    answer: str = Field(max_length=200)


class VoiceInterpretIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    tab: str | None = Field(default=None, max_length=32)  # where they were: a hint, not a limit
    follow_up: VoiceFollowUp | None = None
    input: Literal["voice", "typed"] = "voice"  # spoken, or typed to the assistant (for activity)

    _strip = field_validator("text", mode="before")(_clean)


class VoiceInterpretOut(BaseModel):
    """Cards to confirm; and/or a question with options to tap; and/or a note (why something
    couldn't be done). Nothing has changed yet."""

    proposals: list[VoiceProposal] = []
    question: str | None = None
    options: list[str] = []
    notes: list[str] = []
    command_id: uuid.UUID | None = None  # send back with Confirm (and Undo): each runs only once


class VoiceExecuteIn(BaseModel):
    actions: list[VoiceAction] = Field(min_length=1, max_length=10)
    command_id: uuid.UUID  # from interpret: Confirm and Undo each run once per command
    undo: bool = False  # these are the undos a Confirm of `command_id` returned


class VoiceResult(BaseModel):
    summary: str
    ok: bool
    error: str | None = None
    undo: list[VoiceAction] = []  # send these to /voice/execute to take it back


class VoiceExecuteOut(BaseModel):
    results: list[VoiceResult]


class VoiceConfigOut(BaseModel):
    enabled: bool
