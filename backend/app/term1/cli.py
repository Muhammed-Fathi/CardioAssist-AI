"""Local-only administrator bootstrap and doctor provisioning CLI (C1.2).

There is deliberately **no** public administrator registration endpoint. The
first administrator is created by an operator running this command locally:

    export CARDIOASSIST_DATABASE_URL=sqlite:///./var/cardioassist.sqlite3
    export CARDIOASSIST_IDENTITY_MATCH_KEY=<base64 32+ bytes>
    export CARDIOASSIST_SUBJECT_KEY=<base64 32+ bytes>
    export CARDIOASSIST_PEPPER=<base64 32+ bytes>
    export CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET=<base64 32+ bytes>
    python -m backend.app.term1.cli bootstrap-admin \\
        --email demo.admin@cardioassist.local

The bootstrap secret is read from the environment (or a prompt); it is never a
command-line argument, so it does not appear in shell history or the process
list. The generated administrator password is printed **once** to stdout.

The command is refused if an administrator already exists or if the one-time
bootstrap record is present. Nothing here writes files, logs or secrets.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from . import constants, crypto
from .accounts import bootstrap_administrator, bootstrap_status
from .errors import ApiError
from .settings import SettingsError, load_settings
from .timeutil import Clock
from .tx import read_transaction, write_transaction


def _database():
    from ..storage.database import Database

    return Database()


def _prompt_secret() -> str:
    return getpass.getpass("CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET (input hidden): ").strip()


def _bootstrap_status(args: argparse.Namespace) -> int:
    with read_transaction(_database()) as session:
        state = bootstrap_status(session)
    print(f"administrator_exists={str(state['administrator_exists']).lower()}")
    return 0


def _bootstrap_admin(args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
    except SettingsError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    secret = args.bootstrap_secret or _prompt_secret()
    database = _database()
    password = args.password or crypto.new_temporary_password()
    if crypto.password_problem(password) is not None:
        print("error: the supplied password does not meet the C1 policy.", file=sys.stderr)
        return 2
    try:
        with write_transaction(database) as session:
            result = bootstrap_administrator(
                session,
                clock=Clock(),
                settings=settings,
                bootstrap_secret=secret,
                email=args.email,
                password=password,
            )
    except ApiError as error:
        print(f"refused: {error.code}", file=sys.stderr)
        return 1
    finally:
        database.dispose()
    print(f"user_id={result['user_id']}")
    print(f"email_norm={result['email_norm']}")
    print("administrator_password_once=" + password)
    print("Store the password now; it is not recoverable and is not logged.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.app.term1.cli",
        description="Term 1 C1 local administration (no HTTP administrator signup exists).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("bootstrap-status", help="Report whether an administrator exists.")
    status.set_defaults(func=_bootstrap_status)

    bootstrap = sub.add_parser("bootstrap-admin", help="Create the one-time administrator.")
    bootstrap.add_argument("--email", required=True, help="Synthetic @cardioassist.local address.")
    bootstrap.add_argument(
        "--password",
        default=None,
        help="Administrator password (omit to generate a strong one-time value).",
    )
    bootstrap.add_argument(
        "--bootstrap-secret",
        default=None,
        help="Prefer the environment variable; a CLI value is visible in shell history.",
    )
    bootstrap.set_defaults(func=_bootstrap_admin)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
