"""C1.1a — identity, accounts, sessions, bootstrap, idempotency and audit.

Revision ID: 20261126_02
Revises: 20261017_01
Create Date: 2026-11-26

Creates, in referenced-before-dependent order:

1. ``user_account``      (canonical ``email_norm`` UNIQUE; closed role/status)
2. ``identity_key_check`` (non-secret key-material binding, per purpose/key id)
3. ``doctor_profile``    (FK user_account)
4. ``patient_identity``  (blind indexes only; UNIQUE hmac + canonical subject)
5. ``patient_profile``   (FK user_account + patient_identity, both UNIQUE)
6. ``session``           (verifier-only token storage)
7. ``login_attempt``     (durable per-account / per-source failure counters)
8. ``durable_idempotency`` (actor/operation/target-bound replay identity)
9. ``workflow_audit_event`` (metadata-only; separate from legacy ``audit_event``)
10. ``admin_bootstrap_record`` (single-row duplicate-bootstrap guard)

No legacy table, index or constraint is touched. Infrastructure that C1's
clinical workflow needs is created here rather than deferred (P-25).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261126_02"
down_revision: Union[str, None] = "20261017_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("email_norm", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("password_alg", sa.String(length=32), nullable=False),
        sa.Column("password_version", sa.Integer(), nullable=False),
        sa.Column("password_iterations", sa.Integer(), nullable=False),
        sa.Column("password_salt_b64", sa.String(length=64), nullable=False),
        sa.Column("password_verifier_b64", sa.String(length=64), nullable=False),
        sa.Column("password_change_required", sa.Boolean(), nullable=False),
        sa.Column("status_reason_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("password_changed_at", sa.String(length=32), nullable=True),
        sa.Column("status_changed_at", sa.String(length=32), nullable=True),
        sa.Column("last_login_at", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "role IN ('admin','doctor','patient')", name="ck_user_account_role"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','SUSPENDED','DISABLED')", name="ck_user_account_status"
        ),
        sa.CheckConstraint(
            "password_iterations >= 1 AND password_version >= 1",
            name="ck_user_account_kdf_parameters",
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email_norm", name="ux_user_account_email_norm"),
    )
    op.create_index("ix_user_account_status_role", "user_account", ["status", "role"], unique=False)

    op.create_table(
        "identity_key_check",
        sa.Column("check_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("key_id", sa.String(length=64), nullable=False),
        sa.Column("key_check_hash", sa.String(length=64), nullable=False),
        sa.Column("alg", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("activated_at", sa.String(length=32), nullable=False),
        sa.Column("retired_at", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('identity_match','subject_canonical')",
            name="ck_identity_key_check_purpose",
        ),
        sa.PrimaryKeyConstraint("check_id"),
        sa.UniqueConstraint("purpose", "key_id", name="ux_identity_key_check_purpose_key"),
        sa.UniqueConstraint(
            "purpose", "key_check_hash", name="ux_identity_key_check_purpose_hash"
        ),
    )

    op.create_table(
        "doctor_profile",
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("doctor_id"),
        sa.UniqueConstraint("user_id", name="ux_doctor_profile_user"),
    )
    op.create_index("ix_doctor_profile_active", "doctor_profile", ["active"], unique=False)

    op.create_table(
        "patient_identity",
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("identifier_key_id", sa.String(length=64), nullable=False),
        sa.Column("identifier_hmac", sa.String(length=64), nullable=False),
        sa.Column("canonical_subject_id", sa.String(length=64), nullable=False),
        sa.Column("subject_label", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("identity_id"),
        sa.UniqueConstraint("identifier_hmac", name="ux_patient_identity_hmac"),
        sa.UniqueConstraint("canonical_subject_id", name="ux_patient_identity_subject"),
    )
    op.create_index(
        "ix_patient_identity_key", "patient_identity", ["identifier_key_id"], unique=False
    )

    op.create_table(
        "patient_profile",
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("patient_identity_id", sa.String(length=36), nullable=False),
        sa.Column("display_label", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["patient_identity_id"], ["patient_identity.identity_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("patient_id"),
        sa.UniqueConstraint("user_id", name="ux_patient_profile_user"),
        sa.UniqueConstraint("patient_identity_id", name="ux_patient_profile_identity"),
    )

    op.create_table(
        "session",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_verifier_sha256", sa.String(length=64), nullable=False),
        sa.Column("session_key_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.String(length=32), nullable=False),
        sa.Column("revoked_at", sa.String(length=32), nullable=True),
        sa.Column("revoked_reason", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("token_verifier_sha256", name="ux_session_token_verifier"),
    )
    op.create_index("ix_session_user_expires", "session", ["user_id", "expires_at"], unique=False)
    op.create_index("ix_session_user_revoked", "session", ["user_id", "revoked_at"], unique=False)

    op.create_table(
        "login_attempt",
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("bucket_kind", sa.String(length=16), nullable=False),
        sa.Column("bucket_key_hash", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "bucket_kind IN ('account','source')", name="ck_login_attempt_bucket_kind"
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_index(
        "ix_login_attempt_bucket_time", "login_attempt", ["bucket_key_hash", "created_at"], unique=False
    )
    op.create_index("ix_login_attempt_time", "login_attempt", ["created_at"], unique=False)

    op.create_table(
        "durable_idempotency",
        sa.Column("replay_id", sa.String(length=36), nullable=False),
        sa.Column("replay_scope", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_binding", sa.String(length=96), nullable=False),
        sa.Column("operation", sa.String(length=96), nullable=False),
        sa.Column("target_ref", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("secret_fingerprints_json", sa.JSON(), nullable=False),
        sa.Column("response_public_json", sa.JSON(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("secret_disclosed", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "replay_scope IN ('user','anonymous')", name="ck_durable_idempotency_scope"
        ),
        sa.PrimaryKeyConstraint("replay_id"),
        sa.UniqueConstraint(
            "replay_scope",
            "key_hash",
            "actor_binding",
            "operation",
            "target_ref",
            name="ux_durable_idempotency_identity",
        ),
    )
    op.create_index(
        "ix_durable_idempotency_expiry", "durable_idempotency", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_durable_idempotency_actor",
        "durable_idempotency",
        ["actor_binding", "operation"],
        unique=False,
    )

    op.create_table(
        "workflow_audit_event",
        sa.Column("audit_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=48), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('SUCCESS','FAILED','DENIED','NOT_FOUND','CONFLICT','RATE_LIMITED')",
            name="ck_workflow_audit_outcome",
        ),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_workflow_audit_subject_time",
        "workflow_audit_event",
        ["subject_type", "subject_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_audit_actor_time",
        "workflow_audit_event",
        ["actor_user_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_audit_event_time",
        "workflow_audit_event",
        ["event_type", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_audit_request", "workflow_audit_event", ["request_id"], unique=False
    )

    op.create_table(
        "admin_bootstrap_record",
        sa.Column("bootstrap_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("email_norm", sa.String(length=254), nullable=False),
        sa.Column("bootstrapped_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("bootstrap_id"),
    )


def downgrade() -> None:
    op.drop_table("admin_bootstrap_record")

    op.drop_index("ix_workflow_audit_request", table_name="workflow_audit_event")
    op.drop_index("ix_workflow_audit_event_time", table_name="workflow_audit_event")
    op.drop_index("ix_workflow_audit_actor_time", table_name="workflow_audit_event")
    op.drop_index("ix_workflow_audit_subject_time", table_name="workflow_audit_event")
    op.drop_table("workflow_audit_event")

    op.drop_index("ix_durable_idempotency_actor", table_name="durable_idempotency")
    op.drop_index("ix_durable_idempotency_expiry", table_name="durable_idempotency")
    op.drop_table("durable_idempotency")

    op.drop_index("ix_login_attempt_time", table_name="login_attempt")
    op.drop_index("ix_login_attempt_bucket_time", table_name="login_attempt")
    op.drop_table("login_attempt")

    op.drop_index("ix_session_user_revoked", table_name="session")
    op.drop_index("ix_session_user_expires", table_name="session")
    op.drop_table("session")

    op.drop_table("patient_profile")

    op.drop_index("ix_patient_identity_key", table_name="patient_identity")
    op.drop_table("patient_identity")

    op.drop_index("ix_doctor_profile_active", table_name="doctor_profile")
    op.drop_table("doctor_profile")

    op.drop_table("identity_key_check")

    op.drop_index("ix_user_account_status_role", table_name="user_account")
    op.drop_table("user_account")
