from __future__ import annotations

import logging
import re
from typing import Iterable, List, Sequence, Set

from dataset_pipeline.core.schemas import DialogueSample, MessageRecord
from dataset_pipeline.core.utils import normalise_whitespace, text_digest

logger = logging.getLogger(__name__)


DEFAULT_STOP_PHRASES = {
    "окей",
    "ok",
    "ага",
    "+",
}


def clean_message_text(text: str) -> str:
    text = normalise_whitespace(text)
    text = re.sub(r"(https?://\S+)", r"[URL]", text)
    return text.strip()


def filter_messages(
    messages: Iterable[MessageRecord],
    min_chars: int = 8,
    stop_phrases: Sequence[str] = (),
) -> List[MessageRecord]:
    stops = {phrase.lower() for phrase in (*DEFAULT_STOP_PHRASES, *stop_phrases)}
    filtered: List[MessageRecord] = []
    for msg in messages:
        content = clean_message_text(msg.content)
        if len(content) < min_chars:
            continue
        if content.lower() in stops:
            continue
        filtered.append(msg.copy(update={"content": content}))
    return filtered


def deduplicate_dialogues(pairs: Iterable[DialogueSample]) -> List[DialogueSample]:
    seen: Set[str] = set()
    unique_pairs: List[DialogueSample] = []
    for sample in pairs:
        digest = text_digest(sample.prompt + "\n\n" + sample.completion)
        if digest in seen:
            continue
        seen.add(digest)
        unique_pairs.append(sample)
    return unique_pairs


def deduplicate_messages(messages: Iterable[MessageRecord]) -> List[MessageRecord]:
    seen: Set[str] = set()
    unique: List[MessageRecord] = []
    for msg in messages:
        digest = text_digest(msg.content)
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(msg)
    return unique
