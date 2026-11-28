# Track 2 C2 — Windows OCR worker isolation & private storage runbook

Status: **PROPOSED — OWNER-EXECUTED PROCEDURE.** This procedure has **NOT** been
run on a native Windows host in the contributor sandbox (Linux). Every check
below is marked **OWNER RUN** and must be executed and evidenced by the owner on
a real Windows machine before the document/OCR surface is enabled in a Windows
deployment. No claim of native Windows verification is made here.

It complements the shared `docs/term1/TERM1_WINDOWS_VERIFICATION_RUNBOOK.md`
(Track 1-owned) and covers only the Track 2 additions: the isolated OCR worker
account, the private document root DACL, reparse-point safety, and the strict
worker environment.

## 0. Accounts and roots (OWNER RUN)

Create two **separate** local accounts:

* `cai-backend` — runs the FastAPI backend; owns the private document root and
  the SQLite/DB files; holds the backend secrets (pepper, identity keys).
* `cai-ocr` — runs ONLY the OCR worker; **no** access to backend secrets, the
  database, AI bundles, signing keys, or private research files.

```bat
net user cai-ocr <strong-random-password> /add /comment:"CardioAssist OCR worker"
net localgroup "Users" cai-ocr /add
```

Choose a private document root **outside** the repository working tree, any web
root, and the AI bundle root, e.g. `D:\cai-private\documents`. The backend
settings validator (`settings._validate_doc_root`) refuses a root inside the repo
or overlapping a configured AI/web root; keep the OCR worker's
`CARDIOASSIST_PRIVATE_DOC_DIR` pointing at the SAME root (read-only for it).

## 1. NTFS DACL — backend writer, OCR reader-only (OWNER RUN)

The POSIX model is directories `0750` / files `0640` (backend owner rw, OCR group
read, no world). The Windows equivalent is an explicit DACL: `cai-backend` full
control, `cai-ocr` read-and-execute only, **no** `Everyone` / `Users` /
`Authenticated Users` write or full control.

```bat
:: Remove inherited broad access; grant explicit least privilege.
icacls "D:\cai-private\documents" /inheritance:r
icacls "D:\cai-private\documents" /grant:r "cai-backend:(OI)(CI)F"
icacls "D:\cai-private\documents" /grant:r "cai-ocr:(OI)(CI)RX"
icacls "D:\cai-private\documents" /remove "Everyone" "BUILTIN\Users" "Authenticated Users"
```

The backend opens the root in **writer** mode (it owns the root and applies the
DACL). The OCR worker opens the SAME root with `PrivateDocStore(root,
read_only=True)` (P0-02): it **never** calls `mkdir`, `chmod` or any write — a
separate `cai-ocr` account is not the owner and must not attempt to change
permissions. It only verifies containment + policy and reads verified bytes.

`PrivateDocStore.verify_access_policy()` verifies the DACL **by SID** via the
Windows API (`GetNamedSecurityInfoW` + `GetAce` + `ConvertSidToStringSidW`), NOT by
localized `icacls` principal names (P0-02). It **fails closed** if:

* the DACL is not protected against inheritance (`SE_DACL_PROTECTED` absent), so a
  permissive parent cannot grant broad access;
* the DACL is NULL (unrestricted access);
* any **broad** principal SID — Everyone (`S-1-1-0`), Authenticated Users
  (`S-1-5-11`), `BUILTIN\Users` (`S-1-5-32-545`), Guests (`S-1-5-32-546`),
  INTERACTIVE (`S-1-5-4`), NETWORK (`S-1-5-2`), Power Users (`S-1-5-32-547`) —
  holds an ALLOW ACE with any sensitive **read OR write** right (data/EA/execute,
  DELETE, WRITE_DAC, WRITE_OWNER, GENERIC_READ/WRITE/ALL). This denies unintended
  **read** as well as write;
* the DACL cannot be inspected for any reason.

There is no permissive fallback. The specific `cai-backend` (writer) and `cai-ocr`
(reader) account SIDs are non-broad and are verified by the different-account
checks in §4. The `icacls` commands above SET the DACL; the startup verification
reads it back by SID independent of the OS display language.

Deny the OCR account access to every sensitive root (OWNER RUN):

```bat
icacls "D:\cai-private\db"      /deny "cai-ocr:(OI)(CI)F"
icacls "D:\cai-ai\bundles"      /deny "cai-ocr:(OI)(CI)F"
icacls "D:\cai-ai\signing-keys" /deny "cai-ocr:(OI)(CI)F"
icacls "D:\cai-research"        /deny "cai-ocr:(OI)(CI)F"
```

## 2. Reparse-point / junction safety (code-enforced; OWNER VERIFY)

`storage._win_open_no_reparse` opens files with `FILE_FLAG_OPEN_REPARSE_POINT`
and inspects the opened handle's attributes via `GetFileInformationByHandle`;
any `FILE_ATTRIBUTE_REPARSE_POINT` is refused, so a symlink/junction swapped in
after the ancestor check cannot redirect the open. Every ancestor is also
checked for reparse attributes before opening. The root itself must not be a
reparse point.

OWNER VERIFY: storage keys are `<patient-uuid>/<document-uuid>.bin`, so the
junction must occupy a **valid UUID path component** the store will actually
traverse (a junction named `escape` is never reached). Create a junction named as
a patient UUID pointing outside the root, then attempt to read a key under it:

```bat
:: A valid UUID patient directory replaced by a junction to an outside target.
mklink /J "D:\cai-private\documents\11111111-1111-1111-1111-111111111111" "C:\Windows"
:: Reading key 11111111-.../22222222-2222-2222-2222-222222222222.bin must fail
:: closed (FILE_FLAG_OPEN_REPARSE_POINT + ancestor reparse refusal), never
:: following the junction to C:\Windows.
```

Also verify an **ancestor** junction is refused (P0-02): the constructor walks
every lexical ancestor of the root and refuses any reparse point, so a junction
at a parent of the root (e.g. `D:\cai-private` itself a junction) makes
`PrivateDocStore` refuse to start, in both writer and read-only modes. The
containment decision is made on the lexical path BEFORE `resolve()` collapses any
reparse point, and the read open is handle-relative with `O_NOFOLLOW` semantics so
a component swapped in after the check cannot redirect the open.

## 3. Strict worker environment (OWNER RUN)

A normal `cai-ocr` logon session still carries non-allowlisted variables
(`USERPROFILE`, `APPDATA`, `HOMEPATH`, `COMPUTERNAME`, …), so launching the worker
directly with `set …` + `python -m …worker` would trip `verify_sanitized_env`
(P0-02). Use the **explicit-environment launcher**, which builds an exact
allowlisted environment from a protected config file — never from the inherited
logon environment — and starts the worker with that environment block:

```bat
:: worker-config.json (readable only by cai-ocr) holds ONLY allowlisted keys:
:: {
::   "CARDIOASSIST_OCR_IPC_TOKEN": "<32+ char CSPRNG token>",
::   "CARDIOASSIST_PRIVATE_DOC_DIR": "D:\\cai-private\\documents",
::   "CARDIOASSIST_TESSERACT_CMD": "C:\\ocr\\tesseract\\tesseract.exe",
::   "TESSDATA_PREFIX": "C:\\ocr\\tesseract\\tessdata",
::   "CARDIOASSIST_OCR_FIXTURE_MANIFEST": "D:\\cai-private\\fixture_manifest.json",
::   "PATH": "C:\\Windows\\system32;C:\\Windows;C:\\ocr\\venv\\Scripts",
::   "SYSTEMROOT": "C:\\Windows", "WINDIR": "C:\\Windows",
::   "TEMP": "C:\\ocr\\tmp", "TMP": "C:\\ocr\\tmp", "PATHEXT": ".COM;.EXE;.BAT;.CMD"
:: }
runas /user:cai-ocr "python -m backend.app.term1_c2_documents.windows_launch_worker --config C:\ocr\worker-config.json --port 8765"
```

`windows_launch_worker.build_clean_env` refuses any non-allowlisted config key and
any missing required key, and never inherits the logon environment (only minimal
OS variables may be defaulted). The worker then runs `verify_sanitized_env` on the
clean block and starts. Allowlist: `PATH`, `TESSDATA_PREFIX`, `LANG`, `LC_ALL`,
`CARDIOASSIST_OCR_IPC_TOKEN`, `CARDIOASSIST_PRIVATE_DOC_DIR`,
`CARDIOASSIST_TESSERACT_CMD`, `CARDIOASSIST_OCR_FIXTURE_MANIFEST`, and the minimal
Windows OS set `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`. The worker
enforces the server-owned fixture SHA-256 manifest itself before parsing.

**Exact origin family (P0-02):** `build_server` binds **only** `127.0.0.1` (it
refuses any other host). The backend's `CARDIOASSIST_OCR_WORKER_URL` MUST therefore
be the IPv4 loopback origin `http://127.0.0.1:<port>` — the SAME family the server
listens on. The URL validator also accepts `http://[::1]:<port>`, but the server
does **not** listen on `::1`, so that origin must NOT be used. `localhost`,
credentials, paths, queries and fragments are refused. The IPC client disables
proxies and refuses every redirect, so the bearer token never leaves the origin.

## 4. Different-account isolation checks (OWNER RUN)

These must be executed and the output captured as evidence:

1. **OCR can read a promoted blob** (read-only):
   ```bat
   runas /user:cai-ocr "cmd /c type D:\cai-private\documents\<patient>\<doc>.bin > NUL"
   ```
   Expected: success (read allowed).
2. **OCR cannot write the private root**:
   ```bat
   runas /user:cai-ocr "cmd /c echo x > D:\cai-private\documents\probe.txt"
   ```
   Expected: ACCESS DENIED.
3. **OCR cannot read AI bundles / signing keys / research / DB**:
   ```bat
   runas /user:cai-ocr "cmd /c type D:\cai-ai\bundles\<any> > NUL"
   runas /user:cai-ocr "cmd /c type D:\cai-private\db\<any> > NUL"
   ```
   Expected: ACCESS DENIED for each.
4. **Worker refuses a leaked secret env**:
   ```bat
   set CARDIOASSIST_PEPPER=leaked
   python -m backend.app.term1_c2_documents.worker --port 8765
   ```
   Expected: `WorkerStartupError` (non-allowlisted variable / secret binding).
5. **Worker refuses a non-loopback bind** and the backend refuses a non-loopback
   `CARDIOASSIST_OCR_WORKER_URL` (covered by the cross-platform unit tests; repeat
   on Windows for the owner record).
6. **Worker opens the root read-only** (P0-02): with the worker running as
   `cai-ocr`, confirm it never creates/chmods/writes the root. Attempting a write
   as `cai-ocr` (item 2) must be ACCESS DENIED, and the worker's own
   `PrivateDocStore(root, read_only=True)` performs no `mkdir`/`chmod`/write.
7. **Launcher refuses a polluted config** (P0-02): add a non-allowlisted key
   (e.g. `CARDIOASSIST_PEPPER`) to `worker-config.json` and confirm
   `windows_launch_worker` refuses to start (`LauncherError`), so a leaked secret
   can never reach the worker environment.

## 5. Genuine OCR on Windows (OWNER RUN)

Install native Tesseract (≥ 5.x) + `eng.traineddata`; set
`CARDIOASSIST_TESSERACT_CMD` / `TESSDATA_PREFIX`. Run the C2 suite in the worker
venv and capture the genuine-OCR evidence (PDF text + raster Tesseract). Until
this is executed on Windows, native Windows OCR is **NOT_RUN**; the Linux
evidence in `EVIDENCE.md` is genuine but is not a Windows claim.

## 6. Reporting

Record, per check: the Windows build, the account names, the exact `icacls`
output, the command run, and PASS/FAIL. Attach to the integration checkpoint.
Do not mark any Windows check passed without its captured output.
