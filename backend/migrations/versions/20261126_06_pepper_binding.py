"""C1.1e — durable pepper binding (F1).

Adds a ``pepper_binding`` purpose to ``identity_key_check`` so the operator
pepper is durably bound to the database at initial bootstrap and verified on
every restart. This prevents silent re-binding of replay/rate-limit material
when operator key material is changed without re-initialising the database.

Revision ID: 20261126_06
Revises: 20261126_05
Create Date: 2026-11-26

``pepper_binding`` rows are inserted once on an empty database (during the
first identity-related write via ``verify_or_activate``) and verified read-only
on every startup (via ``verify_startup``). Changed pepper material is detected
because the recomputed check hash no longer matches the stored row.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261126_06"
down_revision: Union[str, None] = "20261126_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite does not support ALTER TABLE DROP CONSTRAINT directly;
    # use batch mode which copies and moves the table.
    with op.batch_alter_table("identity_key_check") as batch_op:
        batch_op.drop_constraint("ck_identity_key_check_purpose")
        batch_op.create_check_constraint(
            "ck_identity_key_check_purpose",
            "purpose IN ('identity_match','subject_canonical','pepper_binding')",
        )


def downgrade() -> None:
    # Revision 05 cannot represent the persisted pepper binding. Never erase
    # that security metadata or start SQLite batch DDL on a bound database.
    # Use a verified pre-upgrade backup for operational rollback instead.
    # Offline SQL generation cannot establish this data-dependent precondition.
    if op.get_context().as_sql:
        raise RuntimeError(
            "C1 downgrade requires online verification of an unbound disposable database."
        )
    connection = op.get_bind()
    # Guard all C1 state, not just pepper metadata: old/corrupt or partially
    # bound databases must not silently lose security or application state.
    c1_tables = (
        "user_account", "doctor_profile", "patient_identity", "patient_profile",
        "identity_key_check", "session", "login_attempt", "verified_visit",
        "patient_invitation", "invitation_attempt", "doctor_patient_assignment",
        "consent_record", "invitation_redemption", "durable_idempotency",
        "workflow_audit_event", "admin_bootstrap_record",
    )
    # All names are fixed migration-owned identifiers, not user input.
    for table in c1_tables:
        if connection.execute(sa.text(f'SELECT 1 FROM "{table}" LIMIT 1')).first() is not None:
            raise RuntimeError(
                "C1 downgrade refused: persisted C1 state is present. "
                "Use an independently verified backup for operational rollback; "
                "in-place downgrade is supported only on disposable databases "
                "without C1 state."
            )
    with op.batch_alter_table("identity_key_check") as batch_op:
        batch_op.drop_constraint("ck_identity_key_check_purpose")
        batch_op.create_check_constraint(
            "ck_identity_key_check_purpose",
            "purpose IN ('identity_match','subject_canonical')",
        )
