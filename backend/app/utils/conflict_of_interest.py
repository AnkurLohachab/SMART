"""Separation-of-duties guards for the model-card lifecycle."""

from __future__ import annotations
import logging
from typing import Optional
from fastapi import HTTPException

from app.db import neo4j_conn

logger = logging.getLogger(__name__)


_ACTION_ROLE = {
    "NFTValidated": "validator",
    "NFTPublished": "publisher",
}


async def _uuid_for_actor(actor_address: str) -> Optional[str]:
    return await neo4j_conn.get_uuid_for_address(actor_address)


async def assert_no_conflict_of_interest(
    token_id: int,
    actor_address: str,
    action: str,
) -> None:
    """Raise HTTPException(403) if actor_address resolves to a UUID with a conflicting role on this card."""
    actor_uuid = await _uuid_for_actor(actor_address)
    if not actor_uuid:
        return

    actors = await neo4j_conn.get_card_actors(token_id)
    creator_uuid = actors.get("creator_uuid")

    if creator_uuid and actor_uuid == creator_uuid and action in {
        "validate",
        "reject",
        "request_revision",
        "publish",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "Conflict of interest: you created this model card, so you cannot "
                f"{_action_verb(action)} it. A different reviewer must perform this action."
            ),
        )

    if action == "publish":
        validator_uuid = await _prior_actor_uuid(actors, "NFTValidated")
        if validator_uuid and actor_uuid == validator_uuid:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Conflict of interest: you validated this model card. "
                    "A different publisher must publish it (4-eyes principle)."
                ),
            )


async def _prior_actor_uuid(actors_record: dict, target_action: str) -> Optional[str]:
    """Return the UUID of whoever previously emitted target_action on this card, or None."""
    events = actors_record.get("events") or []
    for ev in events:
        if ev.get("action") == target_action and ev.get("actor"):
            uuid = await neo4j_conn.get_uuid_for_address(ev["actor"])
            if uuid:
                return uuid
    return None


def _action_verb(action: str) -> str:
    return {
        "validate": "validate",
        "reject": "reject",
        "request_revision": "request revisions on",
        "publish": "publish",
        "deprecate": "deprecate",
    }.get(action, action)
