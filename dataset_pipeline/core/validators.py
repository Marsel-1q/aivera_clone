from __future__ import annotations

import logging
import re
from typing import Iterable, List

from .schemas import DialogueSample, KnowledgeChunk

logger = logging.getLogger(__name__)

MIN_PROMPT_WORDS = 3
MIN_COMPLETION_WORDS = 5
TRASH_RESPONSES = {
    "ок",
    "окей",
    "ok",
    "ок.",
    "да",
    "ага",
    "спасибо",
    "спс",
    "хорошо",
    "ладно",
    "+",
    "++",
    "👍",
}
NON_ALPHANUMERIC_RE = re.compile(r"^\W+$", re.UNICODE)


def _word_count(text: str) -> int:
    return len(text.strip().split())


def _contains_alphanumeric(text: str) -> bool:
    return bool(re.search(r"\w", text, re.UNICODE))


def validate_dialogue_samples(samples: Iterable[DialogueSample]) -> List[DialogueSample]:
    validated: List[DialogueSample] = []
    for sample in samples:
        if not sample.prompt.strip() or not sample.completion.strip():
            logger.debug("Skipping empty prompt/completion from %s", sample.source)
            continue
        prompt = sample.prompt.strip()
        completion = sample.completion.strip()
        if _word_count(prompt) < MIN_PROMPT_WORDS:
            logger.debug("Skipping short prompt from %s", sample.source)
            continue
        if _word_count(completion) < MIN_COMPLETION_WORDS:
            logger.debug("Skipping very short completion from %s", sample.source)
            continue
        completion_lower = completion.lower()
        if completion_lower in TRASH_RESPONSES:
            logger.debug("Skipping trash completion '%s' from %s", completion_lower, sample.source)
            continue
        if NON_ALPHANUMERIC_RE.match(completion) or not _contains_alphanumeric(completion):
            logger.debug("Skipping non-alphanumeric completion from %s", sample.source)
            continue
        validated.append(sample)
    if not validated:
        logger.warning("No valid dialogue samples produced.")
    return validated


def validate_knowledge_chunks(chunks: Iterable[KnowledgeChunk]) -> List[KnowledgeChunk]:
    validated: List[KnowledgeChunk] = []
    for chunk in chunks:
        if len(chunk.content.split()) < 5:
            continue
        validated.append(chunk)
    if not validated:
        logger.warning("No valid knowledge chunks produced.")
    return validated
