from __future__ import annotations

import random
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

from dataset_pipeline.core.schemas import DialogueSample, MessageRecord, ParsedDocument, ParsedMessage
from dataset_pipeline.core.utils import merge_metadata

from .cleaning import deduplicate_dialogues, deduplicate_messages, filter_messages


ASSISTANT_HINTS = {
    "assistant",
    "seller",
    "shop",
    "manager",
    "support",
    "agent",
    "бот",
    "продавец",
    "менеджер",
    "оператор",
    "консультант",
    "админ",
    "support manager",
}

USER_HINTS = {
    "user",
    "customer",
    "client",
    "buyer",
    "клиент",
    "покупатель",
    "заказчик",
    "юзер",
}


def prepare_message_records(
    documents: Iterable[ParsedDocument],
    persona_aliases: Sequence[str],
) -> List[MessageRecord]:
    persona_lower = {alias.lower() for alias in persona_aliases}
    records: List[MessageRecord] = []

    for doc in documents:
        if doc.doc_type != "dialogue":
            continue
        base_metadata = doc.metadata or {}
        for order, parsed in enumerate(doc.messages):
            role = _classify_role(parsed, persona_lower)
            metadata = merge_metadata(base_metadata, parsed.metadata)
            metadata.setdefault("parser_type", doc.parser_type)
            metadata.setdefault("order", order)
            record = MessageRecord(
                role=role,  # type: ignore[arg-type]
                content=parsed.content,
                source=doc.source,
                sender=parsed.sender,
                timestamp=parsed.timestamp,
                metadata=metadata,
            )
            records.append(record)
    return records


def _classify_role(message: ParsedMessage, persona_aliases: set[str]) -> str:
    if message.role in {"user", "assistant"}:
        return message.role

    sender_lower = (message.sender or "").strip().lower()
    if sender_lower in persona_aliases:
        return "assistant"

    def hint_to_role(hint: str | None) -> str | None:
        if not hint:
            return None
        hint = hint.lower()
        if hint in persona_aliases or hint in ASSISTANT_HINTS:
            return "assistant"
        if hint in USER_HINTS:
            return "user"
        return None

    for hint in (sender_lower, message.metadata.get("role"), message.metadata.get("sender")):
        role = hint_to_role(hint if isinstance(hint, str) else None)
        if role:
            return role

    return "user"


def messages_to_prompt(messages: Sequence[MessageRecord]) -> str:
    formatted = []
    for message in messages:
        sender = message.sender or message.role
        formatted.append(f"{sender}: {message.content}")
    return "\n".join(formatted).strip()


def build_multi_turn_pairs(messages: Iterable[MessageRecord]) -> List[DialogueSample]:
    grouped: Dict[str, List[MessageRecord]] = defaultdict(list)
    for msg in messages:
        chat_id = msg.metadata.get("chat_id") or msg.metadata.get("chat_key")
        chat_name = msg.metadata.get("chat_name")
        key = str(chat_id) if chat_id is not None else chat_name or msg.source
        grouped[key].append(msg)

    samples: List[DialogueSample] = []
    for key, group_messages in grouped.items():
        ordered = sorted(
            group_messages,
            key=lambda m: (
                m.timestamp.isoformat() if m.timestamp else "",
                m.metadata.get("message_id") or m.metadata.get("order", 0),
            ),
        )
        filtered = deduplicate_messages(filter_messages(ordered))
        assistant_indices = [idx for idx, msg in enumerate(filtered) if msg.role == "assistant"]
        if not assistant_indices:
            continue
        last_idx = assistant_indices[-1]
        if last_idx == 0:
            continue
        history = filtered[: last_idx + 1]
        prompt_messages = history[:-1]
        if not prompt_messages:
            continue
        prompt_text = messages_to_prompt(prompt_messages)
        completion = history[-1].content.strip()
        if not completion:
            continue
        sample_metadata = {
            "chat_key": key,
            "turn_count": len(history),
            "parser_type": history[-1].metadata.get("parser_type"),
        }
        sample = DialogueSample(
            prompt=prompt_text,
            completion=completion,
            source=history[-1].source,
            messages=list(history),
            metadata=sample_metadata,
        )
        samples.append(sample)

    return deduplicate_dialogues(samples)


def split_dialogues(
    samples: Sequence[DialogueSample],
    eval_ratio: float,
    seed: int,
) -> Tuple[List[DialogueSample], List[DialogueSample]]:
    if not samples:
        return [], []
    shuffled = list(samples)
    random.Random(seed).shuffle(shuffled)
    split_index = int(len(shuffled) * (1 - eval_ratio))
    split_index = max(1, split_index) if len(shuffled) > 1 else 1
    train = shuffled[:split_index]
    eval_split = shuffled[split_index:]
    if not eval_split and train:
        eval_split = [train.pop()]
    return train, eval_split
