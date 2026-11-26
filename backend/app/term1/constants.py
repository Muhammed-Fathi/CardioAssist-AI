"""Closed vocabularies for the Term 1 C1 identity/auth/enrollment stage.

Every enum in this module is closed: the database CHECK constraints, the
request schemas under ``shared/contracts/term1/`` and the service code all use
these values. Adding a value is a contract change, not a code tweak.
"""

from __future__ import annotations

# --- account lifecycle (P-22) -------------------------------------------------
ROLE_ADMIN = "admin"
ROLE_DOCTOR = "doctor"
ROLE_PATIENT = "patient"
ROLES = (ROLE_ADMIN, ROLE_DOCTOR, ROLE_PATIENT)

STATUS_ACTIVE = "ACTIVE"
STATUS_SUSPENDED = "SUSPENDED"
STATUS_DISABLED = "DISABLED"
ACCOUNT_STATUSES = (STATUS_ACTIVE, STATUS_SUSPENDED, STATUS_DISABLED)

# ACTIVE<->SUSPENDED are reversible, everything else terminates in DISABLED.
ALLOWED_STATUS_TRANSITIONS = {
    STATUS_ACTIVE: (STATUS_SUSPENDED, STATUS_DISABLED),
    STATUS_SUSPENDED: (STATUS_ACTIVE, STATUS_DISABLED),
    STATUS_DISABLED: (),
}

# --- password KDF (P-01/P-02) -------------------------------------------------
PASSWORD_ALG = "pbkdf2_hmac_sha256"
PASSWORD_KDF_VERSION = 1
PASSWORD_KDF_ITERATIONS = 600_000
PASSWORD_SALT_BYTES = 16
PASSWORD_KEY_BYTES = 32
PASSWORD_MIN_BYTES = 12
PASSWORD_MAX_BYTES = 128

# --- session lifetime (P-03/P-04) --------------------------------------------
SESSION_ABSOLUTE_SECONDS = 8 * 60 * 60
SESSION_IDLE_SECONDS = 30 * 60
SESSION_TOKEN_BYTES = 32
SESSION_KEY_ID = "session-v1"

# --- login rate limiting (P-06/P-24) -----------------------------------------
LOGIN_FAILURE_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_LOCK_SECONDS = 15 * 60
LOGIN_ATTEMPT_RETENTION_SECONDS = 24 * 60 * 60

# --- invitation lifecycle (P-07/P-08/P-24) -----------------------------------
INVITATION_TOKEN_BYTES = 32
INVITATION_TTL_DEFAULT_SECONDS = 24 * 60 * 60
INVITATION_TTL_MIN_SECONDS = 60 * 60
INVITATION_TTL_MAX_SECONDS = 72 * 60 * 60
INVITATION_MAX_ATTEMPTS = 5
INVITATION_ATTEMPT_RETENTION_SECONDS = 24 * 60 * 60

# Derived invitation status (never stored; computed from timestamps).
INVITATION_ACTIVE = "ACTIVE"
INVITATION_CONSUMED = "CONSUMED"
INVITATION_REVOKED = "REVOKED"
INVITATION_EXPIRED = "EXPIRED"

# --- identity binding (P-09/P-10/P-11) ---------------------------------------
DEMO_ID_PATTERN = r"^DEMO-ID-[0-9]{3,6}$"
DEMO_EMAIL_DOMAIN = "@cardioassist.local"

IDENTITY_MATCH_PURPOSE = "identity_match"
SUBJECT_CANONICAL_PURPOSE = "subject_canonical"
IDENTITY_PURPOSES = (IDENTITY_MATCH_PURPOSE, SUBJECT_CANONICAL_PURPOSE)

IDENTITY_KEY_ALG = "hmac_sha256"

# Domain separators (exact byte encodings; see docs/term1 architecture §3.4).
DOMAIN_IDENTITY_MATCH = "invitation-subject-match/v1"
DOMAIN_SUBJECT_CANONICAL = "term1-subject-canonical/v1"
DOMAIN_SUBJECT_LABEL = "term1-subject-label/v1"
DOMAIN_KEY_CHECK = "identity-key-check/v1"
DOMAIN_INVITATION_VERIFIER = "invitation-verifier/v1"
DOMAIN_SESSION_VERIFIER = "session-verifier/v1"
DOMAIN_RATE_BUCKET = "rate-bucket/v1"
DOMAIN_IDEMPOTENCY_KEY = "idempotency-key/v1"
DOMAIN_REQUEST_FINGERPRINT = "request-fingerprint/v1"
DOMAIN_SECRET_FINGERPRINT = "secret-fingerprint/v1"
DOMAIN_UNKNOWN_CODE_DIGEST = "unknown-invitation-code/v1"

# --- verified visit attestation (closed vocabulary) --------------------------
ATTESTATION_PRIOR_IN_PERSON = "PRIOR_IN_PERSON_VISIT_DEMO"
ATTESTATION_PRIOR_TELEHEALTH = "PRIOR_TELEHEALTH_VISIT_DEMO"
ATTESTATION_CODES = (ATTESTATION_PRIOR_IN_PERSON, ATTESTATION_PRIOR_TELEHEALTH)

# --- consent ------------------------------------------------------------------
CONSENT_KIND_SYNTHETIC_DEMO = "synthetic_demo"
CONSENT_SCOPE_PATIENT_WIDE = "patient_wide_synthetic_demo"
CONSENT_CONTRACT_VERSION = "term1-c1-v1"

# --- redemption flow ----------------------------------------------------------
REDEMPTION_FLOW_REGISTER = "register"
REDEMPTION_FLOW_LINK = "link"
REDEMPTION_FLOWS = (REDEMPTION_FLOW_REGISTER, REDEMPTION_FLOW_LINK)

# --- durable idempotency (P-17) ----------------------------------------------
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
REPLAY_SCOPE_USER = "user"
REPLAY_SCOPE_ANONYMOUS = "anonymous"
REPLAY_SCOPES = (REPLAY_SCOPE_USER, REPLAY_SCOPE_ANONYMOUS)

# Operation identity is the exact method + path template (never a raw URL).
OP_LOGIN = "POST /v1/auth/login"
OP_LOGOUT = "POST /v1/auth/logout"
OP_ME = "GET /v1/auth/me"
OP_REFRESH = "POST /v1/auth/refresh"
OP_PASSWORD = "POST /v1/me/password"
OP_SESSIONS = "GET /v1/me/sessions"
OP_SESSION_REVOKE = "DELETE /v1/me/sessions/{session_id}"
OP_ADMIN_DOCTORS = "POST /v1/admin/doctors"
OP_ADMIN_STATUS = "PATCH /v1/admin/accounts/{user_id}/status"
OP_VISIT_CREATE = "POST /v1/doctor/verified-visits"
OP_VISIT_GET = "GET /v1/doctor/verified-visits/{visit_id}"
OP_INVITATION_CREATE = "POST /v1/doctor/verified-visits/{visit_id}/invitations"
OP_INVITATION_REVOKE = "POST /v1/doctor/invitations/{invitation_id}/revoke"
OP_INVITATION_GET = "GET /v1/doctor/invitations/{invitation_id}"
OP_REGISTER = "POST /v1/patients/register"
OP_LINK = "POST /v1/patients/link"
OP_ASSIGNMENTS = "GET /v1/me/assignments"
OP_ASSIGNMENT_DOCTOR_REVOKE = "POST /v1/doctor/assignments/{assignment_id}/revoke"
OP_ASSIGNMENT_PATIENT_REVOKE = "POST /v1/me/assignments/{assignment_id}/revoke"
OP_CONSENT_REVOKE = "POST /v1/me/consent/synthetic-demo/revoke"

# --- workflow audit vocabulary (metadata only) -------------------------------
EVENT_ADMIN_BOOTSTRAPPED = "ADMIN_BOOTSTRAPPED"
EVENT_ACCOUNT_PROVISIONED = "ACCOUNT_PROVISIONED"
EVENT_ACCOUNT_STATUS_CHANGED = "ACCOUNT_STATUS_CHANGED"
EVENT_LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
EVENT_LOGIN_FAILED = "LOGIN_FAILED"
EVENT_LOGOUT = "LOGOUT"
EVENT_SESSION_REFRESHED = "SESSION_REFRESHED"
EVENT_SESSION_REVOKED = "SESSION_REVOKED"
EVENT_PASSWORD_CHANGED = "PASSWORD_CHANGED"
EVENT_VISIT_ATTESTED = "VISIT_ATTESTED"
EVENT_INVITATION_ISSUED = "INVITATION_ISSUED"
EVENT_INVITATION_REVOKED = "INVITATION_REVOKED"
EVENT_INVITATION_ATTEMPT_FAILED = "INVITATION_ATTEMPT_FAILED"
EVENT_INVITATION_CONSUMED = "INVITATION_CONSUMED"
EVENT_PATIENT_REGISTERED = "PATIENT_REGISTERED"
EVENT_PATIENT_LINKED = "PATIENT_LINKED"
EVENT_ASSIGNMENT_REVOKED = "ASSIGNMENT_REVOKED"
EVENT_CONSENT_REVOKED = "CONSENT_REVOKED"
EVENT_IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
EVENT_AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
EVENT_IDENTITY_KEY_VERIFIED = "IDENTITY_KEY_VERIFIED"
WORKFLOW_EVENT_TYPES = (
    EVENT_ADMIN_BOOTSTRAPPED,
    EVENT_ACCOUNT_PROVISIONED,
    EVENT_ACCOUNT_STATUS_CHANGED,
    EVENT_LOGIN_SUCCEEDED,
    EVENT_LOGIN_FAILED,
    EVENT_LOGOUT,
    EVENT_SESSION_REFRESHED,
    EVENT_SESSION_REVOKED,
    EVENT_PASSWORD_CHANGED,
    EVENT_VISIT_ATTESTED,
    EVENT_INVITATION_ISSUED,
    EVENT_INVITATION_REVOKED,
    EVENT_INVITATION_ATTEMPT_FAILED,
    EVENT_INVITATION_CONSUMED,
    EVENT_PATIENT_REGISTERED,
    EVENT_PATIENT_LINKED,
    EVENT_ASSIGNMENT_REVOKED,
    EVENT_CONSENT_REVOKED,
    EVENT_IDEMPOTENT_REPLAY,
    EVENT_AUTHORIZATION_DENIED,
    EVENT_IDENTITY_KEY_VERIFIED,
)

OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_FAILED = "FAILED"
OUTCOME_DENIED = "DENIED"
OUTCOME_NOT_FOUND = "NOT_FOUND"
OUTCOME_CONFLICT = "CONFLICT"
OUTCOME_RATE_LIMITED = "RATE_LIMITED"
OUTCOMES = (
    OUTCOME_SUCCESS,
    OUTCOME_FAILED,
    OUTCOME_DENIED,
    OUTCOME_NOT_FOUND,
    OUTCOME_CONFLICT,
    OUTCOME_RATE_LIMITED,
)

# Stable audit subject types. ``unknown_invitation`` is the only subject type
# whose subject_id is NULL: an unresolvable access code has no resource id.
SUBJECT_USER_ACCOUNT = "user_account"
SUBJECT_DOCTOR_PROFILE = "doctor_profile"
SUBJECT_PATIENT_PROFILE = "patient_profile"
SUBJECT_SESSION = "session"
SUBJECT_VERIFIED_VISIT = "verified_visit"
SUBJECT_INVITATION = "patient_invitation"
SUBJECT_UNKNOWN_INVITATION = "unknown_invitation"
SUBJECT_ASSIGNMENT = "doctor_patient_assignment"
SUBJECT_CONSENT = "consent_record"
SUBJECT_IDENTITY_KEYS = "identity_key_check"
AUDIT_SUBJECT_TYPES = (
    SUBJECT_USER_ACCOUNT,
    SUBJECT_DOCTOR_PROFILE,
    SUBJECT_PATIENT_PROFILE,
    SUBJECT_SESSION,
    SUBJECT_VERIFIED_VISIT,
    SUBJECT_INVITATION,
    SUBJECT_UNKNOWN_INVITATION,
    SUBJECT_ASSIGNMENT,
    SUBJECT_CONSENT,
    SUBJECT_IDENTITY_KEYS,
)

# --- fixed public labels -----------------------------------------------------
TEMP_PASSWORD_POLICY_ONE_TIME = "one_time_secret"
TEMP_PASSWORD_POLICIES = (TEMP_PASSWORD_POLICY_ONE_TIME,)
SUBJECT_LABEL_PREFIX = "DEMO-SUBJECT-"
