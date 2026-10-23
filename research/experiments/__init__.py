"""Guarded, Windows-local D-047 exploratory experiment runner.

Importing this package never reads local datasets or performs model fitting.
The parser, source reader, and evaluation core are intentionally not exported as
package-level helpers; real-data execution must go through the guarded CLI.
"""
from research.experiments.config import DEFAULT_CONFIG, ExperimentConfig

__all__ = ["DEFAULT_CONFIG", "ExperimentConfig"]
