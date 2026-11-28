"""Isolated local OCR worker daemon (separate unprivileged OS account).

Loopback-only HTTP/JSON service exposing two Track 2 operations:

* ``POST /internal/ocr/v1/validate`` — bounded structural admission validation;
* ``POST /internal/ocr/v1/extract``  — genuine PDF text / raster OCR extraction.

Isolation properties (accepted design §4.3 / §5.3, corrections T2-R3/T2-R4):

* binds strictly to ``127.0.0.1``; zero external/browser access;
* mandatory ``Authorization: Bearer <CSPRNG_IPC_TOKEN>`` checked with
  ``hmac.compare_digest``;
* STRICT allowlisted environment: only the worker's own settings and a minimal
  OS locale/path set may be present. Startup fails closed if ANY non-allowlisted
  variable (including every backend secret / AI bundle binding) is present;
* the worker enforces the server-owned fixture SHA-256 allowlist ITSELF, before
  parsing: a request whose digest is not in the manifest, or whose declared
  template/size/media disagrees with the manifest entry, is rejected without
  reading or parsing the document;
* strict request schemas (exact keys/types), bounded simultaneous TCP
  connections AND parser jobs, an absolute wall-clock request deadline (body read
  + parse), and a per-socket header read deadline (P0-03);
* every parse runs in an isolated, terminable spawn-child process: a parser
  blocked in native pdfminer/PDFium/Tesseract code is hard-killed at the deadline
  and reaped, so the next valid request still succeeds (P0-03);
* the worker opens the private root READ-ONLY (no mkdir/chmod/write) and has zero
  OS read access to AI bundles, signing keys or private research files (enforced
  by the separate account / DACL; see the runbook) (P0-02).

Run::

    CARDIOASSIST_OCR_IPC_TOKEN=... CARDIOASSIST_PRIVATE_DOC_DIR=... \\
    CARDIOASSIST_TESSERACT_CMD=... TESSDATA_PREFIX=... \\
    python -m backend.app.term1_c2_documents.worker --port 8765
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import constants as C
from .fixture_manifest import FixtureManifest, load_manifest
from .ocr_engine import OcrEngineConfig
from .parser_process import (
    ParserContainmentError,
    parse_inprocess,
    run_parse_isolated,
)
from .storage import IntegrityError, PrivateDocStore, StorageError

# Strict environment allowlist (T2-R4). Anything else fails startup closed.
_ALLOWED_ENV = frozenset({
    "PATH", "TESSDATA_PREFIX", "LANG", "LC_ALL",
    "CARDIOASSIST_OCR_IPC_TOKEN", "CARDIOASSIST_PRIVATE_DOC_DIR",
    "CARDIOASSIST_TESSERACT_CMD", "CARDIOASSIST_OCR_FIXTURE_MANIFEST",
    # Minimal Windows OS variables required to launch a subprocess / CRT.
    "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT",
})
# Backend secrets that must NEVER be present (defence in depth; also caught by
# the allowlist, but named explicitly for a clear startup error).
_FORBIDDEN_ENV = (
    "CARDIOASSIST_IDENTITY_MATCH_KEY",
    "CARDIOASSIST_SUBJECT_KEY",
    "CARDIOASSIST_PEPPER",
    "CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET",
    "CARDIOASSIST_LOCAL_BUNDLE_DIR",
    "CARDIOASSIST_LOCAL_TRUSTED_ROOT",
    "CARDIOASSIST_LOCAL_HMAC_KEY_PATH",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class WorkerStartupError(RuntimeError):
    """The worker environment is not safely isolated; refuse to start."""


def verify_sanitized_env(environ: dict[str, str]) -> None:
    """Fail closed unless the environment is exactly the strict allowlist."""
    leaked_secrets = [name for name in _FORBIDDEN_ENV if environ.get(name)]
    if leaked_secrets:
        raise WorkerStartupError(
            "OCR worker environment leaks backend/AI secret bindings: "
            + ", ".join(sorted(leaked_secrets))
        )
    unexpected = sorted(name for name in environ if name not in _ALLOWED_ENV)
    if unexpected:
        raise WorkerStartupError(
            "OCR worker environment carries non-allowlisted variables: "
            + ", ".join(unexpected)
        )


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.match(value))


def _is_byte_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= C.FILE_CAP_BYTES


class WorkerCore:
    """Shared validate/extract logic used by the daemon and the in-process client.

    The server-owned fixture manifest is enforced here, inside the worker,
    before any document byte is read or parsed (T2-R4).
    """

    def __init__(self, store: PrivateDocStore, engine_config: OcrEngineConfig,
                 manifest: FixtureManifest, *, isolated: bool = False) -> None:
        self._store = store
        self._engine = engine_config
        self._manifest = manifest
        # P0-03: the daemon runs every parse in an isolated, terminable child
        # process so a blocked native parser and its descendants are killed at
        # the deadline. The in-process local test client keeps isolated=False for
        # speed. If process-tree cleanup cannot be proven, poison this daemon
        # rather than dispatching another parse with a leaked child.
        self._isolated = isolated
        self._parser_poisoned = False

    @property
    def parser_poisoned(self) -> bool:
        return self._parser_poisoned

    def _read(self, storage_key: str, content_sha256: str, byte_size: int) -> bytes:
        return self._store.read_verified(
            storage_key, expected_sha256=content_sha256, expected_size=byte_size
        )

    def _parse(self, kind: str, data: bytes, media_type: str, deadline: float | None) -> dict:
        if self._parser_poisoned:
            return {
                "ok": False, "code": "worker_unavailable",
                "reason": "parser_containment_failed",
            }
        if self._isolated:
            dl = deadline if deadline is not None else (
                time.monotonic() + C.WORKER_REQUEST_DEADLINE_SECONDS)
            try:
                result = run_parse_isolated(kind, data, media_type, self._engine, dl)
            except ParserContainmentError:
                self._parser_poisoned = True
                return {
                    "ok": False, "code": "worker_unavailable",
                    "reason": "parser_containment_failed",
                }
            if result.get("reason") == "process_tree_isolation_failed":
                # The parser was not released, but this worker cannot establish
                # its containment boundary. Refuse further dispatches rather
                # than retrying a broken isolation setup on every request.
                self._parser_poisoned = True
                return {
                    "ok": False, "code": "worker_unavailable",
                    "reason": "parser_containment_failed",
                }
            return result
        return parse_inprocess(kind, data, media_type, self._engine)

    def _manifest_gate(self, *, content_sha256: str, fixture_file_sha256: str,
                       byte_size: int, media_type: str,
                       fixture_template_id: str | None) -> str | None:
        """Return an error code if the request is not on the server allowlist."""
        if not (_is_sha(content_sha256) and _is_sha(fixture_file_sha256)):
            return "invalid_document_content"
        if content_sha256 != fixture_file_sha256:
            return "invalid_document_content"
        entry = self._manifest.lookup(content_sha256)
        if entry is None:
            return "invalid_document_content"
        if not _is_byte_size(byte_size) or byte_size != entry.byte_size:
            return "invalid_document_content"
        if media_type != entry.media_type:
            return "invalid_document_content"
        if fixture_template_id is not None and fixture_template_id != entry.template_id:
            return "invalid_document_content"
        return None

    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str, fixture_file_sha256: str,
                 deadline: float | None = None) -> dict:
        gate = self._manifest_gate(
            content_sha256=content_sha256, fixture_file_sha256=fixture_file_sha256,
            byte_size=byte_size, media_type=media_type, fixture_template_id=None,
        )
        if gate is not None:
            return {"ok": False, "code": gate}
        try:
            data = self._read(storage_key, content_sha256, byte_size)
        except (IntegrityError, StorageError):
            return {"ok": False, "code": "document_integrity_mismatch"}
        return self._parse("validate", data, media_type, deadline)

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str,
                fixture_file_sha256: str, deadline: float | None = None) -> dict:
        if not isinstance(document_id, str) or not _UUID.match(document_id):
            return {"ok": False, "code": "malformed_request"}
        gate = self._manifest_gate(
            content_sha256=content_sha256, fixture_file_sha256=fixture_file_sha256,
            byte_size=byte_size, media_type=media_type,
            fixture_template_id=fixture_template_id,
        )
        if gate is not None:
            return {"ok": False, "code": gate}
        try:
            data = self._read(storage_key, content_sha256, byte_size)
        except (IntegrityError, StorageError):
            return {"ok": False, "code": "document_integrity_mismatch"}
        result = self._parse("extract", data, media_type, deadline)
        if result.get("ok"):
            # Bind the exact request identity into the response (T2-R4); the
            # client re-checks every echo before trusting any value.
            result = {
                **result,
                "document_id": document_id,
                "content_sha256": content_sha256,
                "fixture_template_id": fixture_template_id,
            }
        return result


# Exact request schemas (T2-R4): unknown keys / wrong types are refused.
_VALIDATE_KEYS = {"storage_key", "content_sha256", "byte_size", "declared_media_type",
                  "fixture_file_sha256"}
_EXTRACT_KEYS = {"document_id", "storage_key", "content_sha256", "byte_size",
                 "declared_media_type", "fixture_template_id", "fixture_file_sha256"}


def _schema_ok(request: dict, keys: set[str]) -> bool:
    if set(request) != keys:
        return False
    if not isinstance(request.get("storage_key"), str):
        return False
    if not _is_sha(request.get("content_sha256")):
        return False
    if not _is_sha(request.get("fixture_file_sha256")):
        return False
    if not _is_byte_size(request.get("byte_size")):
        return False
    if request.get("declared_media_type") not in C.ALLOWED_MEDIA_TYPES:
        return False
    if "fixture_template_id" in keys and request.get("fixture_template_id") not in C.FIXTURE_TEMPLATES:
        return False
    if "document_id" in keys and not (
        isinstance(request.get("document_id"), str) and _UUID.match(request["document_id"])
    ):
        return False
    return True


class _RequestDeadlineExceeded(Exception):
    """The absolute request deadline elapsed while reading the request (P0-03)."""


class _DeadlineSocketReader:
    """Small socket-backed file reader with an absolute deadline on every recv.

    ``BufferedReader.readline`` can perform multiple receives, each with a fresh
    socket timeout, so a peer that dribbles request headers can outlive a single
    per-read timeout indefinitely. This reader checks the monotonic deadline on
    each receive while retaining any bytes read past a line boundary for the
    body reader.
    """

    def __init__(self, connection: socket.socket, deadline: float) -> None:
        self._connection = connection
        self._deadline = deadline
        self._buffer = bytearray()
        self.closed = False

    def _recv(self, size: int, *, header: bool) -> bytes:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout("Absolute OCR worker request deadline exceeded.")
        timeout = min(C.WORKER_READ_TIMEOUT_SECONDS, remaining) if header else remaining
        self._connection.settimeout(timeout)
        return self._connection.recv(size)

    def readline(self, size: int = -1) -> bytes:
        if self.closed or size == 0:
            return b""
        limit = 65537 if size is None or size < 0 else size
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0 and newline + 1 <= limit:
                take = newline + 1
                result = bytes(self._buffer[:take])
                del self._buffer[:take]
                return result
            if len(self._buffer) >= limit:
                result = bytes(self._buffer[:limit])
                del self._buffer[:limit]
                return result
            try:
                chunk = self._recv(min(4096, limit - len(self._buffer)), header=True)
            except socket.timeout:
                raise
            if not chunk:
                result = bytes(self._buffer)
                self._buffer.clear()
                return result
            self._buffer.extend(chunk)

    def read1(self, size: int = -1) -> bytes:
        if self.closed or size == 0:
            return b""
        limit = 65536 if size is None or size < 0 else size
        if self._buffer:
            take = min(limit, len(self._buffer))
            result = bytes(self._buffer[:take])
            del self._buffer[:take]
            return result
        return self._recv(limit, header=False)

    def close(self) -> None:
        self.closed = True
        self._buffer.clear()


def _handler_factory(core: WorkerCore, token: str, slots: threading.BoundedSemaphore):
    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            # Start the absolute deadline before parsing even the request line.
            # The socket-backed reader checks it on every header/body receive, so
            # byte dribbling cannot reset a per-read timeout indefinitely.
            self._deadline = time.monotonic() + C.WORKER_REQUEST_DEADLINE_SECONDS
            self.connection.settimeout(C.WORKER_READ_TIMEOUT_SECONDS)
            self.rfile.close()
            self.rfile = _DeadlineSocketReader(self.connection, self._deadline)

        def _read_body(self, length: int) -> bytes:
            """Read exactly ``length`` bytes under the absolute request deadline.

            ``read1`` performs a single recv per iteration so a client that
            dribbles one byte at a time cannot reset a per-read timeout forever:
            the monotonic deadline is re-checked every iteration (P0-03).
            """
            chunks: list[bytes] = []
            remaining = length
            while remaining > 0:
                timeout = self._deadline - time.monotonic()
                if timeout <= 0:
                    raise _RequestDeadlineExceeded()
                self.connection.settimeout(timeout)
                try:
                    chunk = self.rfile.read1(min(remaining, 65536))
                except socket.timeout as error:
                    raise _RequestDeadlineExceeded() from error
                if time.monotonic() >= self._deadline:
                    raise _RequestDeadlineExceeded()
                if not chunk:
                    raise OSError("Client closed the connection mid-body.")
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)

        def log_message(self, *args):  # noqa: D401 - no document content in logs
            pass

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            if len(body) > C.OCR_IPC_RESPONSE_CAP_BYTES:
                body = json.dumps({"ok": False, "code": "worker_unavailable",
                                   "reason": "response_cap"}).encode("utf-8")
                status = 503
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            auth = self.headers.get("Authorization", "")
            scheme, _, presented = auth.partition(" ")
            if scheme.lower() != "bearer" or not hmac.compare_digest(presented, token):
                self._send(401, {"ok": False, "code": "authentication_required"})
                return
            if self.path not in (C.IPC_VALIDATE_PATH, C.IPC_EXTRACT_PATH):
                self._send(404, {"ok": False, "code": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            if length <= 0 or length > C.FILE_CAP_BYTES + C.MAX_METADATA_FIELD_BYTES:
                self._send(413, {"ok": False, "code": "payload_too_large"})
                return
            try:
                raw_body = self._read_body(length)
            except _RequestDeadlineExceeded:
                self._send(408, {"ok": False, "code": "worker_unavailable",
                                 "reason": "deadline_exceeded"})
                return
            except (OSError, ValueError):
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            try:
                request = json.loads(raw_body.decode("utf-8"))
            except (ValueError, UnicodeError):
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            if not isinstance(request, dict):
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            keys = _VALIDATE_KEYS if self.path == C.IPC_VALIDATE_PATH else _EXTRACT_KEYS
            if not _schema_ok(request, keys):
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            # Bounded simultaneous parser jobs (T2-R4). A saturated worker
            # refuses immediately rather than queueing unbounded work.
            if not slots.acquire(blocking=False):
                self._send(503, {"ok": False, "code": "worker_unavailable", "reason": "busy"})
                return
            try:
                if core.parser_poisoned:
                    self._send(503, {
                        "ok": False, "code": "worker_unavailable",
                        "reason": "parser_containment_failed",
                    })
                    return
                if self.path == C.IPC_VALIDATE_PATH:
                    result = core.validate(
                        storage_key=request["storage_key"],
                        content_sha256=request["content_sha256"],
                        byte_size=request["byte_size"],
                        media_type=request["declared_media_type"],
                        fixture_file_sha256=request["fixture_file_sha256"],
                        deadline=self._deadline,
                    )
                else:
                    result = core.extract(
                        document_id=request["document_id"],
                        storage_key=request["storage_key"],
                        content_sha256=request["content_sha256"],
                        byte_size=request["byte_size"],
                        media_type=request["declared_media_type"],
                        fixture_template_id=request["fixture_template_id"],
                        fixture_file_sha256=request["fixture_file_sha256"],
                        deadline=self._deadline,
                    )
            finally:
                slots.release()
            status = (
                200 if result.get("ok")
                else 503 if result.get("code") == "worker_unavailable"
                else 422
            )
            self._send(status, result)

    return Handler


class _BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with bounded CONNECTION admission (P0-03).

    Plain ``ThreadingHTTPServer`` spawns a handler thread per connection BEFORE
    any parser semaphore is reached, so an attacker could exhaust threads with
    idle/slow connections. Here a connection slot is acquired at accept time; a
    saturated server refuses the connection immediately. The slot is released
    when the handler thread finishes, independent of the parser-job semaphore.
    """

    daemon_threads = True

    def __init__(self, address, handler, connection_slots: threading.BoundedSemaphore):
        self._connection_slots = connection_slots
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            # Too many concurrent connections: refuse immediately, no thread.
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            # Thread creation failed before the handler could release the slot.
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


def build_server(*, host: str = "127.0.0.1", port: int, store: PrivateDocStore,
                 engine_config: OcrEngineConfig, token: str, manifest: FixtureManifest,
                 max_concurrency: int = C.WORKER_MAX_CONCURRENCY,
                 max_connections: int = C.WORKER_MAX_CONNECTIONS) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise WorkerStartupError("OCR worker must bind strictly to 127.0.0.1.")
    if not token or len(token) < 32:
        raise WorkerStartupError("OCR IPC token must be a >= 32-char CSPRNG secret.")
    if max_concurrency < 1:
        raise WorkerStartupError("OCR worker concurrency bound must be >= 1.")
    if max_connections < max_concurrency:
        raise WorkerStartupError("Connection bound must be >= the parser concurrency bound.")
    slots = threading.BoundedSemaphore(max_concurrency)
    connection_slots = threading.BoundedSemaphore(max_connections)
    # P0-03: the daemon isolates every parse in a terminable child process.
    core = WorkerCore(store, engine_config, manifest, isolated=True)
    return _BoundedThreadingHTTPServer(
        (host, port), _handler_factory(core, token, slots), connection_slots)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    verify_sanitized_env(dict(os.environ))
    token = os.environ.get("CARDIOASSIST_OCR_IPC_TOKEN", "")
    doc_dir = os.environ.get("CARDIOASSIST_PRIVATE_DOC_DIR", "")
    if not doc_dir:
        raise WorkerStartupError("CARDIOASSIST_PRIVATE_DOC_DIR is required.")
    engine_config = OcrEngineConfig(
        tesseract_cmd=os.environ.get("CARDIOASSIST_TESSERACT_CMD", "tesseract"),
        tessdata_dir=os.environ.get("TESSDATA_PREFIX") or None,
    )
    # P0-02: the OCR worker opens the private root READ-ONLY. It never creates,
    # chmods or writes; the backend account owns the root and applies permissions.
    store = PrivateDocStore(Path(doc_dir), read_only=True)
    manifest_path = os.environ.get("CARDIOASSIST_OCR_FIXTURE_MANIFEST")
    manifest = load_manifest(Path(manifest_path)) if manifest_path else load_manifest()
    server = build_server(port=args.port, store=store, engine_config=engine_config,
                          token=token, manifest=manifest)
    print(f"OCR worker listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
