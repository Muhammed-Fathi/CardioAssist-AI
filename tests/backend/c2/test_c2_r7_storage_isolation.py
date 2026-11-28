"""Residual P0-02 regressions: read-only worker storage access, ancestor
containment, TOCTOU-safe reads and locale-independent Windows ACL policy.

Reviewer residual review #7235517859: the constructor unconditionally chmods the
shared root (a read-only OCR account is not the owner and cannot chmod); the
Windows ACL check matched English principal names and write only; the ancestor
reparse/containment check vanished after ``resolve()``. These lock the fixes.

The Windows DACL *reader* is Windows-only and NOT_RUN here; its policy decision is
a pure, locale-independent function (``_acl_violation``) exercised on Linux with
synthetic ACEs. Native Windows verification remains an owner procedure.
"""

from __future__ import annotations

import hashlib
import os
import stat
import uuid
from pathlib import Path

import pytest

from backend.app.term1_c2_documents.storage import (
    IntegrityError,
    PrivateDocStore,
    StorageError,
    _acl_violation,
    make_storage_key,
)

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"


def _blob():
    return (FIXTURES / "resting_text.pdf").read_bytes()


def _promote(store):
    data = _blob()
    key = make_storage_key(str(uuid.uuid4()), str(uuid.uuid4()))
    store.promote(store.stage(data, key), key)
    return key, hashlib.sha256(data).hexdigest(), len(data)


# --- read-only worker access ------------------------------------------------
def test_read_only_store_never_chmods(tmp_path, monkeypatch):
    root = tmp_path / "docs"
    PrivateDocStore(root)  # backend writer owns + chmods the root
    mode_before = stat.S_IMODE(os.stat(root).st_mode)

    # A read-only OCR account is NOT the owner: chmod would fail. Prove the
    # read-only constructor never even attempts it.
    def deny_chmod(*_a, **_k):
        raise PermissionError("read-only account cannot chmod")

    monkeypatch.setattr(os, "chmod", deny_chmod)
    reader = PrivateDocStore(root, read_only=True)  # must succeed without chmod
    assert reader.read_only is True
    assert stat.S_IMODE(os.stat(root).st_mode) == mode_before  # unchanged


def test_writer_constructor_would_chmod_and_fail_if_not_owner(tmp_path, monkeypatch):
    # Contrast: the writer constructor DOES chmod, so a non-owner writer fails
    # closed (this is why the worker must use read_only=True).
    def deny_chmod(*_a, **_k):
        raise PermissionError("not owner")

    monkeypatch.setattr(os, "chmod", deny_chmod)
    with pytest.raises(StorageError):
        PrivateDocStore(tmp_path / "docs")


def test_read_only_store_refuses_all_writes(tmp_path):
    root = tmp_path / "docs"
    writer = PrivateDocStore(root)
    key, sha, size = _promote(writer)
    reader = PrivateDocStore(root, read_only=True)
    # Reads work.
    assert reader.read_verified(key, expected_sha256=sha, expected_size=size) == _blob()
    # Every mutating operation is refused.
    with pytest.raises(StorageError):
        reader.stage(_blob(), make_storage_key(str(uuid.uuid4()), str(uuid.uuid4())))
    with pytest.raises(StorageError):
        reader.promote(key, key)
    with pytest.raises(StorageError):
        reader.remove(key)
    with pytest.raises(StorageError):
        reader.discard_staging(key + ".tmp-0000000000000000")
    assert reader.exists(key)  # the blob is untouched


def test_read_only_store_does_not_create_missing_root(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(StorageError):
        PrivateDocStore(missing, read_only=True)
    assert not missing.exists()  # no mkdir in read-only mode


# --- ancestor containment ---------------------------------------------------
def test_symlink_ancestor_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "docs").mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    # 'link' is a symlink ancestor of the root: resolve() would collapse it, but
    # the lexical ancestor walk refuses it (P0-02).
    with pytest.raises(StorageError):
        PrivateDocStore(link / "docs")
    with pytest.raises(StorageError):
        PrivateDocStore(link / "docs", read_only=True)


def test_root_itself_symlink_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(StorageError):
        PrivateDocStore(link)


@pytest.mark.skipif(os.name == "nt", reason="POSIX dir_fd read path")
def test_read_refuses_swapped_patient_dir_symlink(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    key, sha, size = _promote(store)
    patient_id = key.split("/")[0]
    patient_dir = store.root / patient_id
    # Swap the patient directory for a symlink pointing outside the root AFTER
    # the blob was promoted: the handle-relative O_NOFOLLOW open must refuse it.
    outside = tmp_path / "outside"
    outside.mkdir()
    for entry in patient_dir.iterdir():
        entry.rename(outside / entry.name)
    patient_dir.rmdir()
    patient_dir.symlink_to(outside, target_is_directory=True)
    with pytest.raises(IntegrityError):
        store.read_verified(key, expected_sha256=sha, expected_size=size)


@pytest.mark.skipif(os.name == "nt", reason="POSIX O_NOFOLLOW read path")
def test_read_refuses_final_file_symlink(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    key, sha, size = _promote(store)
    target = store.root / key
    outside = tmp_path / "outside.bin"
    outside.write_bytes(_blob())
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(IntegrityError):
        store.read_verified(key, expected_sha256=sha, expected_size=size)


# --- POSIX policy fails closed ----------------------------------------------
def test_verify_policy_refuses_world_and_group_write(tmp_path):
    root = tmp_path / "docs"
    store = PrivateDocStore(root)
    os.chmod(root, 0o777)
    with pytest.raises(StorageError):
        store.verify_access_policy()
    os.chmod(root, 0o770)
    with pytest.raises(StorageError):
        store.verify_access_policy()
    os.chmod(root, 0o750)
    store.verify_access_policy()  # acceptable again


# --- Windows ACL policy (pure, locale-independent; reader is NOT_RUN) --------
def test_acl_violation_broad_principal_read_is_denied():
    # Everyone with GENERIC_READ: unintended READ must be denied (P0-02).
    assert _acl_violation([("S-1-1-0", 0x80000000, 0)], dacl_protected=True) is not None
    # Authenticated Users with FILE_READ_DATA.
    assert _acl_violation([("S-1-5-11", 0x00000001, 0)], dacl_protected=True) is not None


def test_acl_violation_broad_principal_write_is_denied():
    assert _acl_violation([("S-1-5-32-545", 0x00000002, 0)], dacl_protected=True) is not None
    assert _acl_violation([("S-1-1-0", 0x00040000, 0)], dacl_protected=True) is not None  # WRITE_DAC


def test_acl_violation_specific_account_allowed():
    # A specific (non-broad) account SID with full control is the backend writer.
    assert _acl_violation([("S-1-5-21-1-2-3-1001", 0x10000000, 0)], dacl_protected=True) is None
    # Administrators (management) are not in the broad set.
    assert _acl_violation([("S-1-5-32-544", 0x10000000, 0)], dacl_protected=True) is None


def test_acl_violation_unprotected_dacl_fails_closed():
    assert _acl_violation([], dacl_protected=False) is not None


def test_acl_violation_deny_ace_ignored():
    # A DENY ACE (type 1) grants nothing; a broad DENY is fine.
    assert _acl_violation([("S-1-1-0", 0x80000000, 1)], dacl_protected=True) is None


def test_acl_violation_clean_dacl_passes():
    aces = [
        ("S-1-5-21-1-2-3-1001", 0x10000000, 0),  # backend writer full
        ("S-1-5-21-1-2-3-1002", 0x00000001 | 0x00000020, 0),  # OCR reader read+execute
    ]
    assert _acl_violation(aces, dacl_protected=True) is None


# --- clean-environment Windows launcher (P0-02; build_clean_env is portable) --
def _worker_config():
    return {
        "CARDIOASSIST_OCR_IPC_TOKEN": "c2-test-launcher-token-0000000000001",
        "CARDIOASSIST_PRIVATE_DOC_DIR": "D:\\cai-private\\documents",
        "CARDIOASSIST_TESSERACT_CMD": "C:\\ocr\\tesseract\\tesseract.exe",
        "TESSDATA_PREFIX": "C:\\ocr\\tesseract\\tessdata",
        "PATH": "C:\\Windows\\system32;C:\\ocr\\venv\\Scripts",
        "SYSTEMROOT": "C:\\Windows",
    }


def test_launcher_allowlist_matches_worker():
    from backend.app.term1_c2_documents.windows_launch_worker import ALLOWED_ENV
    from backend.app.term1_c2_documents.worker import _ALLOWED_ENV
    assert ALLOWED_ENV == _ALLOWED_ENV


def test_launcher_builds_exact_allowlisted_env():
    from backend.app.term1_c2_documents.windows_launch_worker import ALLOWED_ENV, build_clean_env
    env = build_clean_env(_worker_config())
    assert set(env) <= ALLOWED_ENV
    assert env["CARDIOASSIST_PRIVATE_DOC_DIR"] == "D:\\cai-private\\documents"


def test_launcher_refuses_non_allowlisted_key():
    from backend.app.term1_c2_documents.windows_launch_worker import LauncherError, build_clean_env
    cfg = _worker_config()
    cfg["CARDIOASSIST_PEPPER"] = "leaked"  # a backend secret must never pass
    with pytest.raises(LauncherError):
        build_clean_env(cfg)


def test_launcher_refuses_missing_required_key():
    from backend.app.term1_c2_documents.windows_launch_worker import LauncherError, build_clean_env
    cfg = _worker_config()
    del cfg["CARDIOASSIST_OCR_IPC_TOKEN"]
    with pytest.raises(LauncherError):
        build_clean_env(cfg)


def test_launcher_does_not_inherit_logon_env():
    from backend.app.term1_c2_documents.windows_launch_worker import build_clean_env
    # A polluted logon environment is NOT inherited: only config + minimal OS
    # defaults appear, and a leaked secret in os_defaults is ignored.
    env = build_clean_env(_worker_config(), os_defaults={
        "SYSTEMROOT": "C:\\Windows", "CARDIOASSIST_PEPPER": "leaked", "RANDOM_VAR": "x"})
    assert "CARDIOASSIST_PEPPER" not in env and "RANDOM_VAR" not in env
