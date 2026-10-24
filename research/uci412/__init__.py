"""Source-specific UCI-412 CAD research benchmark (synthetic-only until authorized).

Importing this package reads the committed plan and feature dictionary and
validates them against in-code invariants. It never reads a dataset, never fits a
model, and never writes an artifact.

Governance: the registered plan is a proposal. No real-data run is authorized by
this package alone; a separate, locally signed, hash-bound M3a authorization is
required, and Gate PT P-3 remains CLOSED.
"""
from research.uci412.config import DEFAULT_CONFIG, Uci412Config

__all__ = ["DEFAULT_CONFIG", "Uci412Config"]
