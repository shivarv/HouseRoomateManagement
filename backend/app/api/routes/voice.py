import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.voice import (
    VoiceConfigOut,
    VoiceExecuteIn,
    VoiceExecuteOut,
    VoiceInterpretIn,
    VoiceInterpretOut,
)
from app.services import households as household_svc
from app.services import voice

router = APIRouter(tags=["voice"])


@router.get("/voice/config", response_model=VoiceConfigOut)
def voice_config(user: CurrentUser):
    """Whether to show the mic button (voice needs a Claude API key on the server)."""
    return VoiceConfigOut(enabled=voice.enabled())


@router.post("/households/{household_id}/voice/interpret", response_model=VoiceInterpretOut)
def interpret(household_id: uuid.UUID, body: VoiceInterpretIn, db: DbSession, user: CurrentUser):
    """What they said → cards to confirm, a question back, or why not. Changes nothing."""
    me = household_svc.require_membership(db, household_id, user)
    return voice.interpret(db, user, me, body)


@router.post("/households/{household_id}/voice/execute", response_model=VoiceExecuteOut)
def execute(household_id: uuid.UUID, body: VoiceExecuteIn, db: DbSession, user: CurrentUser):
    """Runs confirmed actions (or their undos) through the usual services. All are checked first:
    if any can't be done, none run and that one has an `error`."""
    me = household_svc.require_membership(db, household_id, user)
    return VoiceExecuteOut(results=voice.execute(db, me, body.actions))
