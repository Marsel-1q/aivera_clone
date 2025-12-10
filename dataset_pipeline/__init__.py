"""
Pure parsing pipeline for persona-aligned AI clones.

The dataset pipeline loads heterogeneous sources through rule-based, OCR, or
hybrid parsers, normalises and deduplicates multi-turn conversations, and
exports validated train/validation splits plus factual knowledge chunks.
"""

from importlib.metadata import version, PackageNotFoundError

__all__ = ["__version__"]

try:
    __version__ = version("dataset_pipeline")
except PackageNotFoundError:  # pragma: no cover - local editable install
    __version__ = "0.1.0"
