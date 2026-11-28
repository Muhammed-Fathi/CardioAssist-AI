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

`PrivateDocStore.verify_access_policy()` runs `icacls` at startup and **fails
closed** if a broad principal has `(F)`, `(M)`, `(W)`, `(WD)`, `(WE)` or `(DC)`,
or if `icacls` cannot inspect the DACL. There is no permissive fallback.

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

OWNER VERIFY: create a junction inside the root pointing outside it and confirm
the store refuses to read/write through it:

```bat
mklink /J "D:\cai-private\documents\escape" "C:\Windows"
:: Attempting to stage/read a key whose path traverses 'escape' must fail closed.
```

## 3. Strict worker environment (OWNER RUN)

Launch the worker **as `cai-ocr`** with ONLY the allowlisted variables. Any other
variable (including every backend secret) makes `verify_sanitized_env` refuse
startup.

```bat
:: Run in a clean logon session for cai-ocr (no inherited backend env).
set CARDIOASSIST_OCR_IPC_TOKEN=<32+ char CSPRNG token>
set CARDIOASSIST_PRIVATE_DOC_DIR=D:\cai-private\documents
set CARDIOASSIST_TESSERACT_CMD=C:\ocr\tesseract\tesseract.exe
set TESSDATA_PREFIX=C:\ocr\tesseract\tessdata
set CARDIOASSIST_OCR_FIXTURE_MANIFEST=D:\cai-private\fixture_manifest.json
python -m backend.app.term1_c2_documents.worker --port 8765
```

Allowlist: `PATH`, `TESSDATA_PREFIX`, `LANG`, `LC_ALL`,
`CARDIOASSIST_OCR_IPC_TOKEN`, `CARDIOASSIST_PRIVATE_DOC_DIR`,
`CARDIOASSIST_TESSERACT_CMD`, `CARDIOASSIST_OCR_FIXTURE_MANIFEST`, and the minimal
Windows OS set `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`. The worker
enforces the server-owned fixture SHA-256 manifest itself before parsing.

The backend dials the worker at an **exact parsed loopback origin**
(`http://127.0.0.1:<port>` or `http://[::1]:<port>`); `localhost`, credentials,
paths, queries and fragments are refused. The IPC client disables proxies and
refuses every redirect, so the bearer token never leaves the origin.

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
