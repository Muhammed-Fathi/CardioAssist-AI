"""Seal, verify and (only then) publish RH-04 gate evidence.

**Why this module exists.** Revision 1 validated evidence in Stage 5 and uploaded
it later. Two files were written *after* the scan (``lane-a/classified.json`` by
Stage 6, ``gate-summary.json`` by the aggregate), so they were published without
ever being validated. That is not a detector weakness; it is a **lifecycle**
defect: the set of files that was validated was never the set of files that was
uploaded, and nothing proved the two were the same.

Revision 2 replaces "scan a directory, then upload from that directory" with:

    finalize -- seal -- verify -- upload exactly one artifact

**The seal is the security boundary.** `seal_publication` does five things in one
process, in this order:

1. resolves the allowlist to an explicit set of files;
2. refuses anything that is not a regular file — symlinks, hardlinked files with a
   link count above 1, directories, sockets, devices, anything outside the tree;
3. validates **content** (JSON schema, forbidden patterns) before anything is
   copied;
4. **copies** the validated bytes into a fresh staging directory the workflow did
   not previously write to, then re-validates the copies and compares per-file
   SHA-256 digests with the originals. If a file changes between validation and
   copy, the digests differ and the seal aborts;
5. writes `MANIFEST.json` into the staging package — path, size and SHA-256 for
   every member — plus `SHA256SUMS` in `sha256sum -c` format.

The upload step then uploads **the staged directory only**, and
`verify_sealed_package` re-derives every digest from the bytes on disk immediately
before the upload step runs. A mutation after the seal is caught there; a mutation
between verify and upload is bounded by the trust boundary documented below.

**What this cannot do.** It cannot make a GitHub Actions runner trustworthy. Every
step runs as the same user on the same filesystem, so anything that can write the
evidence tree can also write the package. What the seal buys is *detectability* and
*ordering*: no writer can run after the seal without the verify step failing, and
the manifest makes a substitution visible after the fact. The residual window is
documented in `TRUST_BOUNDARY` so it is not mistaken for a guarantee.

**Never print content.** Failures name a path, a rule and a count. The manifest is
built from digests and sizes. Nothing in this module emits file content into a log.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from research.intake.rh04_v2_evidence_security import (
    ALLOWED_FILES,
    FORBIDDEN_PATTERNS,
    MAX_FILE_BYTES,
    SecurityFailure,
    check_payload,
)

__all__: Final[tuple[str, ...]] = (
    "PUBLICATION_ALLOWLIST",
    "HOST_PUBLICATION_ALLOWLIST",
    "MANIFEST_NAME",
    "MANIFEST_DIGEST_NAME",
    "SumsEntry",
    "SealedPackage",
    "PublicationIntegrityError",
    "seal_publication",
    "verify_sealed_package",
    "read_manifest",
    "TRUST_BOUNDARY",
)


class PublicationIntegrityError(Exception):
    """The publication package is not what was validated.

    The message is assembled from paths, rule names, counts and digests only. It
    never contains evidence content.
    """


#: Exactly what may be published, and the JSON keys each file must carry.
#: Deliberately a literal, not derived: deriving it from a directory listing is
#: how an unexpected file gets in.
PUBLICATION_ALLOWLIST: Final[dict[str, frozenset[str]]] = dict(ALLOWED_FILES)

#: The host-dispatch evidence set. Named explicitly rather than globbed, and kept
#: separate from the forced-dispatch table so neither can silently absorb a file
#: meant for the other.
HOST_PUBLICATION_ALLOWLIST: Final[dict[str, frozenset[str]]] = {
    "lane-a-host.json": frozenset({"any_failure", "routes", "validity"}),
    "lane-b-host.json": frozenset({"observed_digest", "verdict"}),
}

MANIFEST_NAME: Final[str] = "MANIFEST.json"
MANIFEST_DIGEST_NAME: Final[str] = "SHA256SUMS"

#: Documented residual exposure. Reported, not hidden.
TRUST_BOUNDARY: Final[str] = (
    "Seal and verify run as the same user on the same filesystem as every other "
    "workflow step, so a compromised earlier step can in principle write the "
    "staging directory between verify and upload. The seal makes that detectable "
    "(manifest digests) and orders every legitimate writer before the seal, but it "
    "does not and cannot make the runner trustworthy. Artifacts are immutable once "
    "uploaded; the digest of the zip is recorded by Actions."
)


@dataclass(frozen=True)
class SumsEntry:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SealedPackage:
    root: Path
    entries: tuple[SumsEntry, ...]
    manifest_sha256: str

    @property
    def digest(self) -> str:
        """Manifest identity captured by the sealing or verification operation."""
        return self.manifest_sha256

    def to_record(self) -> dict[str, Any]:
        return {
            "package_root": self.root.as_posix(),
            "package_digest": self.digest,
            "n_files": len(self.entries),
            "files": [
                {"path": entry.path, "sha256": entry.sha256, "bytes": entry.size_bytes}
                for entry in self.entries
            ],
            "trust_boundary": TRUST_BOUNDARY,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_unsafe_file(path: Path, root: Path, rel: str) -> None:
    """Refuse anything that is not a plain, singly-linked regular file."""
    info = path.lstat()
    mode = info.st_mode

    if stat.S_ISLNK(mode):
        raise PublicationIntegrityError(
            f"{rel}: symlink -- refusing to seal a file whose bytes may resolve "
            "outside the evidence tree"
        )
    if not stat.S_ISREG(mode):
        raise PublicationIntegrityError(f"{rel}: not a regular file")
    if info.st_nlink > 1:
        # A hardlink makes the "sealed" bytes aliasable by a writer that keeps the
        # other name. Refused rather than reasoned about.
        raise PublicationIntegrityError(
            f"{rel}: hardlinked (link count {info.st_nlink}) -- a second name for "
            "these bytes could be written after the seal"
        )
    if info.st_size > MAX_FILE_BYTES:
        raise PublicationIntegrityError(
            f"{rel}: {info.st_size} bytes exceeds the {MAX_FILE_BYTES}-byte limit"
        )
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise PublicationIntegrityError(
            f"{rel}: resolves outside the evidence root"
        ) from None


def _walk_dir(root: Path, directory: str) -> set[str]:
    """Every file under one declared evidence directory, strictly checked.

    Symlinked directories are refused too: `os.walk(followlinks=False)` would
    silently skip them, and silently skipping a file is how an unvalidated file
    becomes invisible rather than rejected.
    """
    base = root / directory
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        here = Path(dirpath)
        for name in sorted(dirnames):
            candidate = here / name
            if candidate.is_symlink():
                raise PublicationIntegrityError(
                    f"{candidate.relative_to(root).as_posix()}: symlinked directory "
                    "in the evidence tree"
                )
        for name in sorted(filenames):
            candidate = here / name
            rel = candidate.relative_to(root).as_posix()
            _reject_unsafe_file(candidate, root, rel)
            found.add(rel)
    return found


def _collect_surface(
    root: Path,
    evidence_dirs: Sequence[str],
    table: Mapping[str, frozenset[str]],
) -> set[str]:
    """The exact set of files this seal is allowed to consider.

    **Why this is not a walk of the evidence root.** The workflow runs in the
    repository checkout, so the evidence root is the checkout itself: it holds
    ``.git``, ``research/``, the frozen V1 sources and every other tracked file.
    Walking it would classify all of that as "unexpected evidence" and the gate
    would fail closed on every legitimate run -- a control that cannot pass is
    not a control.

    So the surface is *declared*, and it is the same surface Stage 5 scans:

    * each named evidence directory is enumerated completely, so a file added to
      ``lane-a/`` after the scan is still caught (R24-F01);
    * root-level evidence is limited to the explicitly named allowlist keys, so
      ``gate-summary.json`` is covered without admitting anything beside it
      (R24-F02).

    Anything outside the surface is neither validated nor published: the package
    contains allowlisted members only, so an unlisted file cannot reach the
    upload even in principle.
    """
    found: set[str] = set()
    for directory in evidence_dirs:
        target = root / directory
        if not target.is_dir():
            raise PublicationIntegrityError(
                f"declared evidence directory '{directory}' is absent or not a "
                "directory"
            )
        found |= _walk_dir(root, directory)
    for rel in sorted(table):
        if "/" in rel:
            continue
        candidate = root / rel
        if candidate.exists() or candidate.is_symlink():
            _reject_unsafe_file(candidate, root, rel)
            found.add(rel)
    return found


def seal_publication(
    evidence_root: str | Path,
    staging_root: str | Path,
    *,
    allowlist: Mapping[str, frozenset[str]] | None = None,
    required: Sequence[str] | None = None,
    evidence_dirs: Sequence[str] = ("lane-a", "lane-b"),
) -> SealedPackage:
    """Validate, copy, re-validate and manifest an evidence tree into a package.

    Everything the publication boundary needs happens here, in one process, in
    this order: **resolve -> reject unsafe -> validate content -> copy -> re-validate
    the copies -> compare digests -> write manifest**.
    """
    root = Path(evidence_root)
    staging = Path(staging_root)
    table = dict(allowlist or PUBLICATION_ALLOWLIST)
    required_names = tuple(required) if required is not None else tuple(table)

    if not root.is_dir():
        raise PublicationIntegrityError(
            f"evidence root '{root.as_posix()}' is not a directory"
        )
    if staging.exists():
        # A pre-existing staging directory is not trusted: it may contain files
        # this process did not write.
        raise PublicationIntegrityError(
            f"staging directory '{staging.as_posix()}' already exists; refusing to "
            "seal into a directory that may already hold unvalidated files"
        )

    # 1. Enumerate the DECLARED surface and reject unsafe members before
    #    trusting any path. Not a walk of the checkout: see `_collect_surface`.
    present = _collect_surface(root, evidence_dirs, table)

    # 2. Allowlist resolution: every present file must be publishable, and every
    #    publishable file must be present.
    unexpected = sorted(present - set(table))
    if unexpected:
        raise PublicationIntegrityError(
            "unexpected file(s) in the evidence tree: " + ", ".join(unexpected[:10])
        )
    missing = sorted(set(required_names) - present)
    if missing:
        raise PublicationIntegrityError(
            "required evidence file(s) absent: " + ", ".join(missing)
        )

    # 3. Validate content in place, then 4/5 copy and re-validate.
    #
    # The staging directory is removed if any step below fails, so that "the
    # package directory exists" is equivalent to "the seal succeeded". A
    # half-written package left on disk is the shape of the original defect: a
    # directory that looks publishable and is not.
    staging.mkdir(parents=True, exist_ok=False)
    try:
        return _seal_into(root, staging, table, present)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _seal_into(
    root: Path,
    staging: Path,
    table: Mapping[str, frozenset[str]],
    present: set[str],
) -> SealedPackage:
    entries: list[SumsEntry] = []
    for rel in sorted(table):
        if rel not in present:
            continue
        source = root / rel
        raw = source.read_bytes()
        try:
            check_payload(rel, raw, table=table)
        except SecurityFailure as error:
            raise PublicationIntegrityError(str(error)) from None

        destination = staging / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)

        copied = destination.read_bytes()
        source_digest = hashlib.sha256(raw).hexdigest()
        copied_digest = hashlib.sha256(copied).hexdigest()
        if source_digest != copied_digest:
            raise PublicationIntegrityError(
                f"{rel}: content changed between validation and copy "
                f"({source_digest[:12]} != {copied_digest[:12]}); the seal is void"
            )
        # Re-validate the COPY. If the source mutated after we read it, the bytes
        # we publish are what we just validated -- and we validated them here.
        try:
            check_payload(rel, copied, table=table)
        except SecurityFailure as error:
            raise PublicationIntegrityError(str(error)) from None

        entries.append(
            SumsEntry(path=rel, sha256=copied_digest, size_bytes=len(copied))
        )

    # 6. Manifest, then prove the manifest agrees with the files on disk.
    manifest = {
        "protocol": "rh04-publication-seal-v1",
        "files": [
            {"path": e.path, "sha256": e.sha256, "bytes": e.size_bytes}
            for e in entries
        ],
        "n_files": len(entries),
        "trust_boundary": TRUST_BOUNDARY,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (staging / MANIFEST_NAME).write_bytes(manifest_bytes)
    (staging / MANIFEST_DIGEST_NAME).write_bytes(
        "".join(f"{e.sha256}  {e.path}\n" for e in entries).encode("utf-8")
    )

    expected_digest = hashlib.sha256(manifest_bytes).hexdigest()
    return verify_sealed_package(staging, expected_digest=expected_digest, allowlist=table)


def _manifest_document(raw: bytes) -> dict[str, Any]:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicationIntegrityError("MANIFEST.json: invalid JSON") from None
    if not isinstance(document, dict) or document.get("protocol") != "rh04-publication-seal-v1":
        raise PublicationIntegrityError("MANIFEST.json: invalid protocol or shape")
    if set(document) != {"protocol", "files", "n_files", "trust_boundary"}:
        raise PublicationIntegrityError("MANIFEST.json: unexpected metadata")
    files = document.get("files")
    if (not isinstance(files, list) or not files or type(document.get("n_files")) is not int
            or document["n_files"] != len(files) or document.get("trust_boundary") != TRUST_BOUNDARY):
        raise PublicationIntegrityError("MANIFEST.json: inconsistent metadata")
    return document


def _read_regular(root: Path, rel: str) -> bytes:
    path = root / rel
    _reject_unsafe_file(path, root, rel)
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise PublicationIntegrityError("sealed member exceeds size limit")
    return raw


def read_manifest(package_root: str | Path) -> dict[str, Any]:
    root = Path(package_root)
    return _manifest_document(_read_regular(root, MANIFEST_NAME))


def verify_sealed_package(
    package_root: str | Path, *, expected_digest: str | None = None,
    allowlist: Mapping[str, frozenset[str]] | None = None,
) -> SealedPackage:
    """Check the exact package against a trusted seal digest and content rules.

    The standalone API permits inspection without an external digest; hosted
    publication requires one via the CLI. Neither mode permits arbitrary files.
    The verify-to-upload same-user trust boundary remains unchanged.
    """
    root = Path(package_root)
    if root.is_symlink() or not root.is_dir():
        raise PublicationIntegrityError("package root must be a real directory")
    raw_manifest = _read_regular(root, MANIFEST_NAME)
    manifest_digest = hashlib.sha256(raw_manifest).hexdigest()
    if expected_digest is not None and (not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
            or manifest_digest != expected_digest):
        raise PublicationIntegrityError("manifest differs from trusted seal digest")
    manifest = _manifest_document(raw_manifest)
    recorded: dict[str, tuple[str, int]] = {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes"}:
            raise PublicationIntegrityError("MANIFEST.json: malformed file entry")
        rel, digest, size = entry["path"], entry["sha256"], entry["bytes"]
        if (not isinstance(rel, str) or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest) or type(size) is not int
                or not 0 < size <= MAX_FILE_BYTES or rel in recorded):
            raise PublicationIntegrityError("MANIFEST.json: invalid or duplicate member")
        recorded[rel] = (digest, size)
    if allowlist is None:
        if set(recorded) == set(PUBLICATION_ALLOWLIST):
            allowlist = PUBLICATION_ALLOWLIST
        elif set(recorded) == set(HOST_PUBLICATION_ALLOWLIST):
            allowlist = HOST_PUBLICATION_ALLOWLIST
        else:
            raise PublicationIntegrityError("manifest is not an approved publication file set")
    if set(recorded) != set(allowlist):
        raise PublicationIntegrityError("manifest differs from expected publication file set")
    # Allowlist membership is checked before using any manifest path.
    expected_files = set(recorded) | {MANIFEST_NAME, MANIFEST_DIGEST_NAME}
    expected_dirs = {parent.as_posix() for rel in expected_files
                     for parent in Path(rel).parents if parent != Path(".")}
    on_disk: set[str] = set()
    def walk_error(error: OSError) -> None:
        raise PublicationIntegrityError("package traversal failed") from error
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=walk_error):
        here = Path(dirpath)
        for name in dirnames:
            child = here / name
            if child.is_symlink() or child.relative_to(root).as_posix() not in expected_dirs:
                raise PublicationIntegrityError("unexpected or symlinked package directory")
        for name in filenames:
            child = here / name
            rel = child.relative_to(root).as_posix()
            if rel not in expected_files:
                raise PublicationIntegrityError("unexpected package member")
            _reject_unsafe_file(child, root, rel)
            on_disk.add(rel)
    if on_disk != expected_files:
        raise PublicationIntegrityError("sealed package is incomplete")
    entries: list[SumsEntry] = []
    for rel, (expected_hash, expected_size) in sorted(recorded.items()):
        raw = _read_regular(root, rel)
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected_hash or len(raw) != expected_size:
            raise PublicationIntegrityError(f"{rel}: digest or size mismatch")
        try:
            check_payload(rel, raw, table=allowlist)
        except SecurityFailure as error:
            raise PublicationIntegrityError(f"{rel}: publication content rejected") from error
        entries.append(SumsEntry(path=rel, sha256=actual, size_bytes=len(raw)))
    expected_sums = "".join(f"{e.sha256}  {e.path}\n" for e in entries).encode("utf-8")
    if _read_regular(root, MANIFEST_DIGEST_NAME) != expected_sums:
        raise PublicationIntegrityError("SHA256SUMS differs from the complete manifest")
    return SealedPackage(root=root, entries=tuple(entries), manifest_sha256=manifest_digest)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: `seal <evidence-root> <staging-root>` or `verify <package-root>`."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("evidence_root")
    seal.add_argument("staging_root")
    seal.add_argument("--github-output")
    seal.add_argument(
        "--host-documents",
        action="store_true",
        help="Seal the host-dispatch evidence set instead of the forced set.",
    )
    seal.add_argument(
        "--evidence-dirs",
        nargs="*",
        default=None,
        help=(
            "Declared evidence directories to enumerate, relative to the evidence "
            "root. Must match Stage 5's --evidence-dirs, or the sealed set and the "
            "scanned set would differ. Defaults to lane-a/lane-b for forced "
            "dispatch and to no directories for host dispatch, whose evidence is "
            "two root documents."
        ),
    )
    seal.add_argument(
        "--root-documents",
        nargs="*",
        default=None,
        help=(
            "Root-level evidence documents to seal (defaults to the allowlist's "
            "root-level keys). The host job passes its two host documents here."
        ),
    )
    verify = sub.add_parser("verify")
    verify.add_argument("package_root")
    verify.add_argument("--expected-digest", required=True)
    verify.add_argument("--host-documents", action="store_true")
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "seal":
            table = (
                HOST_PUBLICATION_ALLOWLIST
                if arguments.host_documents
                else PUBLICATION_ALLOWLIST
            )
            if arguments.root_documents is not None:
                # Restrict, never extend: a root document the allowlist does not
                # contain is a configuration error, not a new member.
                unknown = sorted(set(arguments.root_documents) - set(table))
                if unknown:
                    print(
                        json.dumps(
                            {
                                "sealed": False,
                                "error": "root document(s) not on the allowlist: "
                                + ", ".join(unknown),
                                "trust_boundary": TRUST_BOUNDARY,
                            },
                            indent=2,
                            sort_keys=True,
                        )
                    )
                    return 1
                table = {
                    key: schema
                    for key, schema in table.items()
                    if "/" in key or key in set(arguments.root_documents)
                }
            sealed = seal_publication(
                arguments.evidence_root,
                arguments.staging_root,
                allowlist=table,
                required=tuple(table),
                evidence_dirs=tuple(
                    arguments.evidence_dirs
                    if arguments.evidence_dirs is not None
                    else (() if arguments.host_documents else ("lane-a", "lane-b"))
                ),
            )
            if arguments.github_output is not None:
                with open(arguments.github_output, "a", encoding="utf-8") as output:
                    output.write(f"package_digest={sealed.digest}\n")
            print(json.dumps(sealed.to_record(), indent=2, sort_keys=True))
            return 0
        sealed = verify_sealed_package(
            arguments.package_root, expected_digest=arguments.expected_digest,
            allowlist=HOST_PUBLICATION_ALLOWLIST if arguments.host_documents else PUBLICATION_ALLOWLIST,
        )
        print(json.dumps(sealed.to_record(), indent=2, sort_keys=True))
        return 0
    except (PublicationIntegrityError, OSError, ValueError) as error:
        # Do not publish exception contents from untrusted paths or documents.
        print(
            json.dumps(
                {"sealed": False, "error": "publication integrity check failed", "trust_boundary": TRUST_BOUNDARY},
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised via the workflow
    raise SystemExit(main())
