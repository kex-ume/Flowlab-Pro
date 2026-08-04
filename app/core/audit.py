"""Small, explicit audit-trail helper for SDS-controlled records."""

from __future__ import annotations

import json
from typing import Any


def record_audit(
    cursor,
    entity_type: str,
    entity_id: int | None,
    action: str,
    actor: str | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
) -> None:
    """Append an immutable, JSON-safe trace of a controlled action."""
    cursor.execute(
        """
        INSERT INTO audit_trail (
            entity_type, entity_id, action, actor, before_state, after_state
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            entity_id,
            action,
            actor,
            json.dumps(before_state, default=str, sort_keys=True)
            if before_state is not None
            else None,
            json.dumps(after_state, default=str, sort_keys=True)
            if after_state is not None
            else None,
        ),
    )
