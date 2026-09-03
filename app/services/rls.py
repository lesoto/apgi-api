"""
Row-Level Security context propagation (governing doc §7, Postgres RLS
policies in app/alembic/versions/add_research_pilot_domain.py).

RLS policies on participant-scoped tables key off two session GUCs
(`app.current_user_id`, `app.current_role`) that must be set for the
duration of the current transaction. This module is the one place that
sets them, via `SET LOCAL` — scoped to the transaction, never leaking
between requests sharing a pooled connection.

RLS is a second, independent layer here, not the sole access control: an
anonymous participant (no linked user_id) is authorized at the application
layer by possessing the participant_id itself (see app/routes/participants.py),
which RLS cannot express. Always pair `set_rls_context` with an explicit
ownership/permission check in the route handler.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.authorization import Role, TokenPayload


def _effective_role(current_user: Optional[TokenPayload]) -> str:
    if current_user is None:
        return ""
    roles = current_user.roles or []
    if Role.ADMIN.value in roles:
        return "admin"
    if Role.RESEARCHER.value in roles:
        return "researcher"
    return ""


def set_rls_context(db: Session, current_user: Optional[TokenPayload]) -> None:
    """Set the RLS session GUCs for the current transaction.

    No-op on non-Postgres engines (SQLite in tests has no RLS to configure,
    and `SET LOCAL` is not valid SQLite syntax).
    """
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return

    user_id = current_user.user_id if current_user else ""
    role = _effective_role(current_user)

    db.execute(text("SET LOCAL app.current_user_id = :user_id"), {"user_id": user_id})
    db.execute(text("SET LOCAL app.current_role = :role"), {"role": role})
