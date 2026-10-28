"""Regressions for inherited ACLs on newly created private research directories."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai.filesystem_security import (
    create_or_verify_private_directory,
    ensure_private_directory,
    verify_access_control,
)
from ai.uci412_demo import run_uci412_research_demo


def test_created_private_directory_is_hardened_and_verified(tmp_path: Path) -> None:
    target = create_or_verify_private_directory(tmp_path / "new_private" / "child")

    assert target.is_dir()
    assert verify_access_control(
        target, expect_directory=True, strict_private=True
    ).ok


def test_existing_insecure_directory_is_rejected_without_permission_changes(
    tmp_path: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("Native Windows ACL preservation is exercised by the NTFS test below.")

    target = tmp_path / "caller_owned"
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    original_mode = target.stat().st_mode

    with pytest.raises(OSError, match="failed private access-control verification"):
        create_or_verify_private_directory(target)

    assert target.stat().st_mode == original_mode


def test_demo_rejects_insecure_existing_work_root_without_rewriting(
    tmp_path: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("Native Windows inherited-ACL rejection is tested separately.")

    work_root = tmp_path / "insecure_demo_work_root"
    work_root.mkdir()
    work_root.chmod(0o777)
    original_mode = work_root.stat().st_mode

    with pytest.raises(OSError, match="failed private access-control verification"):
        run_uci412_research_demo(budget="smoke", work_dir=work_root)

    assert work_root.stat().st_mode == original_mode


def test_ensure_private_directory_can_harden_a_newly_created_inherited_path(
    tmp_path: Path,
) -> None:
    # This deliberately models a directory that already exists before the
    # security utility is applied, as happens after tempfile.mkdtemp / mkdir.
    target = tmp_path / "inherited_acl_child"
    target.mkdir()
    secured = ensure_private_directory(target)

    assert secured == target
    assert verify_access_control(
        target, expect_directory=True, strict_private=True
    ).ok


@pytest.mark.skipif(os.name != "nt", reason="Requires native Windows NTFS and Win32 SDDL APIs.")
def test_inherited_owner_rights_ace_is_removed_before_private_children_are_used(
    tmp_path: Path,
) -> None:
    """Reproduce inherited OWNER RIGHTS (S-1-3-4) without accepting that ACE."""
    from ai.filesystem_security import (
        _get_win32_api,
        _win32_apply_sddl_dacl,
        _win32_current_user_sid_and_admin,
    )

    user_sid, _ = _win32_current_user_sid_and_admin()
    parent = ensure_private_directory(tmp_path / "owner_rights_parent")
    # Deliberately add an inheritable full-control OWNER RIGHTS entry, alongside
    # the standard secure principals. A plain Path.mkdir child inherits it.
    inherited_owner_rights_sddl = (
        f"D:PAI(A;OICI;FA;;;{user_sid})"
        "(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)"
    )
    _win32_apply_sddl_dacl(parent, inherited_owner_rights_sddl)

    unprotected_child = parent / "plain_mkdir_child"
    unprotected_child.mkdir()
    inherited_acl = verify_access_control(
        unprotected_child, expect_directory=True, strict_private=True
    )
    assert not inherited_acl.ok
    assert "S-1-3-4" in inherited_acl.detail

    # The production creation helper hardens a fresh child, protects its DACL
    # against inheritance, and verifies the resulting binary ACL before use.
    protected_bundle_root = create_or_verify_private_directory(
        parent / "trusted_bundles"
    )
    protected_key_root = create_or_verify_private_directory(parent / "private_keys")
    for directory in (protected_bundle_root, protected_key_root):
        result = verify_access_control(
            directory, expect_directory=True, strict_private=True
        )
        assert result.ok, result.detail

    # An already existing insecure directory is rejected rather than silently
    # rewritten by the create-or-verify operation.
    with pytest.raises(OSError, match="failed private access-control verification"):
        create_or_verify_private_directory(unprotected_child)
    with pytest.raises(OSError, match="failed private access-control verification"):
        run_uci412_research_demo(budget="smoke", work_dir=unprotected_child)
    assert not verify_access_control(
        unprotected_child, expect_directory=True, strict_private=True
    ).ok

    # Keep a reference to the API module alive through this native test; its
    # setup ensures the call above runs against the actual Win32 implementation.
    assert _get_win32_api()["advapi32"] is not None
