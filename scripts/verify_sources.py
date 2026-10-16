"""Verify source-file SHA256 hashes and supervisor classification. No dependencies."""
from pathlib import Path
import csv
import hashlib
from collections import Counter

root = Path(__file__).resolve().parents[1]
folder = root / 'research' / 'source_materials'
manifest = folder / 'SOURCE_MANIFEST.sha256'

for line in manifest.read_text(encoding='utf-8').splitlines():
    expected, filename = line.split('  ', 1)
    actual = hashlib.sha256((folder / filename).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f'SHA256 MISMATCH: {filename}')
    print(f'OK sha256: {filename}')

with (folder / 'literature_review_status.csv').open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
counts = Counter(r['Supervisor_Status'] for r in rows)
expected = {'APPROVED_GREEN': 9, 'MAYBE_PINK': 1, 'MAYBE_ORANGE': 6, 'REJECTED_RED': 9}
if len(rows) != 25 or counts != expected:
    raise SystemExit(f'SUPERVISOR STATUS AUDIT FAILED: rows={len(rows)}, counts={dict(counts)}')
print(f'OK supervisor audit: 25 papers, statuses {dict(counts)}')
