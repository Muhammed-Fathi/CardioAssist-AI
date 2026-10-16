# Source Materials / Dataset Policy

- `research/source_materials/` contains only supplied academic/project *documents* and screening metadata; it contains **no raw clinical dataset**.
- The original 25-paper spreadsheet is preserved for auditability. The CSV is the Arena-compatible first-sheet export with explicit `Supervisor_Status`.
- Respect paper publisher terms; links and metadata are not authorizations to redistribute article PDFs or datasets.
- Do not put patient-level raw data, PHI, credential files, API keys, wearable exports, or trained model weights in this repository.
- For candidate data, first record official URL, study population, target label, terms of use, expected size, split method, version/hash and reproducibility instructions in Phase 0.
- Datasets or weights may be obtained later, **only with approval**, in ignored local directories or separately permissioned storage; all public downloads must follow their licenses.
- Simulated data can test APIs and UI plumbing; do not report model performance on it as clinical evidence.
- Never let protected data leave approved environments or be uploaded to unapproved third-party tools.
