from __future__ import annotations

from typing import Iterable, Iterator

from dataset_pipeline.core.schemas import DialogueSample


def format_samples(samples: Iterable[DialogueSample], target_format: str) -> Iterator[dict]:
    formatter = target_format.lower()
    if formatter == "huggingface":
        yield from (_to_huggingface(sample) for sample in samples)
    elif formatter == "sharegpt":
        yield from (_to_sharegpt(sample) for sample in samples)
    elif formatter == "instruct":
        yield from (_to_instruct(sample) for sample in samples)
    else:
        raise ValueError(f"Unsupported format: {target_format}")


def _to_huggingface(sample: DialogueSample) -> dict:
    messages = [{"role": msg.role, "content": msg.content} for msg in sample.messages]
    return {
        "messages": messages,
        "source": sample.source,
        "metadata": sample.metadata,
    }


def _to_sharegpt(sample: DialogueSample) -> dict:
    def map_role(role: str) -> str:
        return "gpt" if role == "assistant" else "human"

    conversations = [{"from": map_role(msg.role), "value": msg.content} for msg in sample.messages]
    return {
        "conversations": conversations,
        "source": sample.source,
        "metadata": sample.metadata,
    }


def _to_instruct(sample: DialogueSample) -> dict:
    return {
        "instruction": sample.prompt,
        "response": sample.completion,
        "source": sample.source,
        "metadata": sample.metadata,
    }
