"""Track 2 C2 contract source (DOC1–DOC7) for Track 1 shared composition.

These artifacts are Track 2-owned. The core integrator (Track 1) merges them into
``shared/contracts/term1/`` (paths, schemas, error catalogue) and the composed
OpenAPI; Track 2 never edits the shared files directly. ``generate.py`` writes the
YAML/JSON artifacts from the authoritative Python catalogue so code and contract
cannot drift, and ``tests/backend/c2/test_c2_contracts.py`` fails on any mismatch.
"""
