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
    with op.batch_alter_table("identity_key_check") as batch_op:
        batch_op.drop_constraint("ck_identity_key_check_purpose")
        batch_op.create_check_constraint(
            "ck_identity_key_check_purpose",
            "purpose IN ('identity_match','subject_canonical')",
        )
