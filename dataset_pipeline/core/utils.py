from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Tuple

logger = logging.getLogger(__name__)


def iter_source_files(root: Path) -> Iterator[Path]:
    """Yield files from the input directory, ignoring hidden/system entries."""
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            yield path


def normalise_whitespace(text: str) -> str:
    # Collapse repeated whitespace while preserving intentional paragraph breaks.
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_digest(text: str) -> str:
    """Stable identifier for de-duplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def detect_encoding(path: Path) -> str:
    """Heuristic charset detection: default to UTF-8, fallback to cp1251."""
    for encoding in ("utf-8", "utf-16", "cp1251"):
        try:
            with path.open("r", encoding=encoding) as fh:
                fh.read()
                return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def safe_read_text(path: Path) -> str:
    encoding = detect_encoding(path)
    with path.open("r", encoding=encoding, errors="ignore") as fh:
        return fh.read()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value)
    return slug.strip("-").lower()


def ensure_directory(path: Path) -> None:
    os.makedirs(path, exist_ok=True)


def parse_russian_datetime(value: str) -> Optional[datetime]:
    """Support common timestamp formats from messengers."""
    if not value:
        return None
    normalized = value.strip()
    # Try ISO-8601 first (Telegram exports, etc.)
    try:
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    patterns = (
        ("%d.%m.%Y, %H:%M:%S", r"\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}:\d{2}"),
        ("%d.%m.%Y, %H:%M", r"\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}"),
        ("%d.%m.%y, %H:%M", r"\d{2}\.\d{2}\.\d{2}, \d{2}:\d{2}"),
        ("%d.%m.%Y %H:%M", r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}"),
    )
    for fmt, regex in patterns:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            if not re.fullmatch(regex, value):
                continue
    return None


def merge_metadata(base: Dict, extra: Optional[Dict]) -> Dict:
    result = dict(base)
    if extra:
        result.update(extra)
    return result


def chunk_text(text: str, chunk_size: int, overlap: int) -> Iterator[Tuple[int, str]]:
    """Simple sliding window chunker for knowledge documents."""
    words = text.split()
    if not words:
        return
    start = 0
    chunk_index = 0
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunk_words = words[start:end]
        yield chunk_index, " ".join(chunk_words).strip()
        if end == len(words):
            break
        start = max(0, end - overlap)
        chunk_index += 1
