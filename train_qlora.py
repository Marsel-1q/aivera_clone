#!/usr/bin/env python3
"""QLoRA fine-tuning pipeline for Qwen2.5-VL, GLM4V и PaliGemma2 мультимодальные клоны."""

from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset as TorchDataset
from transformers import (
    AutoProcessor,
    BitsAndBytesConfig,
    Glm4vForConditionalGeneration,
    PaliGemmaForConditionalGeneration,
    Qwen2_5_VLForConditionalGeneration,
    Trainer,
    TrainingArguments,
)
from PIL import Image

try:  # pragma: no cover - optional for older transformers
    from transformers.trainer_callback import EarlyStoppingCallback
except ImportError:  # pragma: no cover
    EarlyStoppingCallback = None

try:  # pragma: no cover - optional import depending on transformers version
    from transformers.trainer_utils import IntervalStrategy, SaveStrategy
except ImportError:  # pragma: no cover
    IntervalStrategy = None
    SaveStrategy = None

from qwen_vl_utils import process_vision_info

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrainingRunResult:
    adapter_dir: Path
    output_dir: Path
    train_metrics: Dict[str, Any]


@dataclass(slots=True)
class HistoryConfig:
    max_history_turns: int
    summary_max_chars: int


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QLoRA fine-tuning for мультимодальных VL-клонов.")
    parser.add_argument(
        "--train-file",
        default="data/processed_dataset/style/train.jsonl",
        help="Путь к обучающему датасету (JSONL) из dataset_pipeline.",
    )
    parser.add_argument(
        "--eval-file",
        default="data/processed_dataset/style/eval.jsonl",
        help="Путь к валидационному датасету (JSONL) из dataset_pipeline.",
    )
    parser.add_argument(
        "--knowledge-file",
        default="data/processed_dataset/knowledge/knowledge_chunks.jsonl",
        help="JSONL c фактами/знаниями. Если отсутствует — будет пропущен.",
    )
    parser.add_argument(
        "--model-id",
        default="Qwen/Qwen2.5-VL-7B-Instruct",
        help="ID базовой VL-модели для дообучения.",
    )
    parser.add_argument(
        "--processor-id",
        default=None,
        help="ID процессора (если отличается от model-id). По умолчанию берётся model-id.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Каталог для чекпойнтов Trainer.",
    )
    parser.add_argument(
        "--adapter-dir",
        default="outputs/lora_adapter",
        help="Каталог для сохранения обученного LoRA-адаптера.",
    )
    parser.add_argument(
        "--epochs",
        type=float,
        default=3.0,
        help="Количество эпох обучения.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Размер batch на устройство (VL модели требуют больше памяти).",
    )
    parser.add_argument(
        "--eval-batch-size",
        type=int,
        default=None,
        help="Пер-устройство batch size для валидации. По умолчанию = batch-size.",
    )
    parser.add_argument(
        "--grad-accum",
        type=int,
        default=8,
        help="Шаги аккумуляции градиента.",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-5,
        help="Learning rate для параметров LoRA.",
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=2048,
        help="Максимальная длина токенов (используется для отсечения при препроцессинге).",
    )
    parser.add_argument(
        "--target-modules",
        nargs="+",
        default=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        help="Модули для LoRA адаптации.",
    )
    parser.add_argument(
        "--lora-r",
        type=int,
        default=16,
        help="Параметр rank для LoRA.",
    )
    parser.add_argument(
        "--lora-alpha",
        type=int,
        default=32,
        help="LoRA alpha.",
    )
    parser.add_argument(
        "--lora-dropout",
        type=float,
        default=0.05,
        help="Dropout в LoRA.",
    )
    parser.add_argument(
        "--bf16",
        action="store_true",
        help="Включить bf16 тренировку (рекомендуется, если доступно).",
    )
    parser.add_argument(
        "--tf32",
        action="store_true",
        help="Включить TF32 (полезно на Ampere).",
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Пробрасывать trust_remote_code=True при загрузке модели/процессора.",
    )
    parser.add_argument(
        "--logging-steps",
        type=int,
        default=10,
        help="Частота логирования метрик.",
    )
    parser.add_argument(
        "--persona-name",
        default="",
        help="Имя персоны (используется в системном сообщении).",
    )
    parser.add_argument(
        "--persona-description",
        default=(
            "Ты цифровой клон, отвечаешь естественно, дружелюбно и по делу. "
            "Не добавляй юридические предупреждения или примечания, если я об этом явно не просил. "
            "Ты должен использовать стиль общения твоего оригинала, говорить в точности как твой оригинал. "
            "При обучении запоминай вопросы, которые задаёт человек, и твои ответы, эмоции и знания из knowledge."
        ),
        help="Описание персоны для системного сообщения.",
    )
    parser.add_argument(
        "--system-prompt",
        default="",
        help="Явный системный промт. Если указан, заменяет persona-description.",
    )
    parser.add_argument(
        "--max-history-turns",
        type=int,
        default=12,
        help="Сколько последних сообщений диалога оставлять без сжатия.",
    )
    parser.add_argument(
        "--history-summary-max-chars",
        type=int,
        default=600,
        help="Максимальная длина сводки для ранней части истории.",
    )
    parser.add_argument(
        "--knowledge-repeat",
        type=int,
        default=1,
        help="Повторить знания в обучении указанное число раз.",
    )
    parser.add_argument(
        "--vl-backend",
        choices=["qwen2_vl", "glm4v", "paligemma"],
        help="Бэкенд мультимодели. По умолчанию определяется по model-id.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed для воспроизводимости.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Уровень логирования.",
    )
    parser.add_argument(
        "--eval-steps",
        type=int,
        default=100,
        help="Как часто запускать evaluate (в шагах).",
    )
    parser.add_argument(
        "--save-steps",
        type=int,
        default=200,
        help="Как часто сохранять чекпойнты (в шагах).",
    )
    parser.add_argument(
        "--early-stopping-patience",
        type=int,
        default=3,
        help="Сколько оценок без улучшения ждать перед остановкой.",
    )
    parser.add_argument(
        "--warmup-steps",
        type=int,
        default=100,
        help="Шаги линейного прогрева LR.",
    )
    parser.add_argument(
        "--dataloader-num-workers",
        type=int,
        default=2,
        help="Количество воркеров DataLoader.",
    )
    parser.add_argument(
        "--max-train-samples",
        type=int,
        default=None,
        help="Ограничить размер обучающего датасета (для отладки).",
    )
    parser.add_argument(
        "--max-eval-samples",
        type=int,
        default=None,
        help="Ограничить размер eval датасета.",
    )
    return parser.parse_args(argv)


def infer_backend(model_id: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    lowered = model_id.lower()
    if "qwen" in lowered and "vl" in lowered:
        return "qwen2_vl"
    if "glm" in lowered:
        return "glm4v"
    if "paligemma" in lowered:
        return "paligemma"
    raise ValueError(
        "Не удалось определить мультимодальный бэкенд по model-id. Укажите его явно через --vl-backend."
    )


def ensure_file(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found at {path}")


def load_json_dataset(path: Path) -> Dataset:
    return load_dataset("json", data_files=str(path), split="train")


def load_optional_dataset(path: Path) -> Optional[Dataset]:
    if not path.exists():
        logger.warning("Пропускаю файл %s — не найден.", path)
        return None
    if path.stat().st_size == 0:
        logger.warning("Пропускаю файл %s — пустой.", path)
        return None
    try:
        return load_json_dataset(path)
    except Exception as exc:  # pragma: no cover - защита на случай битого JSON
        logger.warning("Не удалось загрузить %s: %s", path, exc)
        return None


def build_persona_header(persona_name: str, persona_description: str) -> str:
    persona = persona_name.strip() or "цифровой двойник"
    description = persona_description.strip()
    header = f"Ты — {persona}."
    if description:
        header += f" {description}"
    header += (
        " Отвечай естественно, в стиле оригинала. "
        "Перед каждым ответом перечитывай всю историю диалога, чтобы не повторяться. "
        "Приветствуй собеседника только в начале первой реплики, далее переходи сразу к сути. "
        "Если вопрос уточняющий, отвечай кратко и без лишних повторов."
    )
    return header


def dedupe_preserving_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_image_refs(message: Optional[Dict[str, Any]]) -> List[str]:
    if not message:
        return []
    collected: List[str] = []

    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "image":
                ref = block.get("image") or block.get("url") or block.get("path")
                if isinstance(ref, str):
                    collected.append(ref)

    for key in ("images", "image_paths", "media", "attachments"):
        value = message.get(key)
        if not value:
            continue
        if isinstance(value, str):
            collected.append(value)
            continue
        if isinstance(value, dict):
            ref = value.get("path") or value.get("url") or value.get("image")
            if isinstance(ref, str):
                collected.append(ref)
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if isinstance(item, str):
                    collected.append(item)
                elif isinstance(item, dict):
                    ref = item.get("path") or item.get("url") or item.get("image")
                    if isinstance(ref, str):
                        collected.append(ref)

    metadata = message.get("metadata")
    if isinstance(metadata, dict):
        for key in ("images", "attachments", "media"):
            value = metadata.get(key)
            if not value:
                continue
            if isinstance(value, str):
                collected.append(value)
                continue
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    if isinstance(item, str):
                        collected.append(item)
                    elif isinstance(item, dict):
                        ref = item.get("path") or item.get("url") or item.get("image")
                        if isinstance(ref, str):
                            collected.append(ref)

    return dedupe_preserving_order(collected)


def load_image_from_ref(ref: Optional[str]) -> Optional[Image.Image]:
    if not ref:
        return None
    ref = ref.strip()
    if not ref:
        return None
    if ref.startswith("file://"):
        ref = ref[7:]
    path = Path(ref)
    if not path.exists():
        logger.warning("Изображение %s не найдено для GLM.", ref)
        return None
    try:
        with Image.open(path) as img:
            return img.convert("RGB")
    except Exception as exc:
        logger.warning("Не удалось загрузить изображение %s: %s", ref, exc)
        return None


def create_dummy_image(size: Tuple[int, int] = (448, 448), color: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    return Image.new("RGB", size, color=color)


def extract_text_from_block(block: Any) -> str:
    if block is None:
        return ""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str):
                return text
        if "text" in block and isinstance(block["text"], str):
            return block["text"]
        if "content" in block:
            return extract_text_from_block(block["content"])
        if "value" in block and isinstance(block["value"], str):
            return block["value"]
        return ""
    if isinstance(block, (list, tuple)):
        parts = [extract_text_from_block(item) for item in block]
        return " ".join(part for part in parts if part).strip()
    return str(block)


def make_text_block(text: str) -> Dict[str, str]:
    return {"type": "text", "text": text}


def _get_field(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def normalize_plain_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    role = str(_get_field(message, "role") or "user").strip() or "user"
    sender = _get_field(message, "sender")
    raw_content = _get_field(message, "content")
    if raw_content is None:
        raw_content = _get_field(message, "text") or _get_field(message, "value")
    text = extract_text_from_block(raw_content)
    text = " ".join(text.split())
    if not text:
        return None
    normalized: Dict[str, Any] = {"role": role, "content": text}
    if sender:
        normalized["sender"] = sender
    for label in ("emotion", "tone", "topic"):
        value = _get_field(message, label)
        if value:
            normalized[label] = value
    return normalized


def summarize_messages(messages: Sequence[Dict[str, Any]], max_chars: int) -> str:
    if not messages:
        return ""
    fragments: List[str] = []
    for msg in messages:
        sender = msg.get("sender") or msg.get("role") or "собеседник"
        content = msg.get("content", "")
        if not content:
            continue
        fragments.append(f"{sender}: {content}")
    summary = " ".join(fragments).strip()
    if max_chars > 0 and len(summary) > max_chars:
        summary = summary[: max_chars - 3].rsplit(" ", 1)[0].strip() + "..."
    return summary


def apply_history_window(
    messages: Sequence[Dict[str, Any]],
    history_config: HistoryConfig,
) -> List[Dict[str, Any]]:
    if history_config.max_history_turns <= 0 or len(messages) <= history_config.max_history_turns:
        return list(messages)
    if not messages:
        return []

    recent = list(messages[-history_config.max_history_turns :])
    early = list(messages[:-history_config.max_history_turns])
    summary = summarize_messages(early, history_config.summary_max_chars)
    if summary:
        summary_message = {
            "role": "system",
            "content": f"Сводка предыдущих сообщений: {summary}",
        }
        return [summary_message] + recent
    return recent


def plain_to_chat_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    text = message.get("content", "").strip()
    if not text:
        return None
    return {
        "role": message.get("role") or "user",
        "content": [make_text_block(text)],
    }


def build_style_prompt(
    example: Dict[str, Any],
    persona_name: str,
    persona_description: str,
    history_config: HistoryConfig,
) -> Dict[str, Any]:
    messages: Sequence[Dict[str, Any]] = example.get("messages") or []
    target_message: Optional[Dict[str, Any]] = None
    context_messages: Sequence[Dict[str, Any]]

    if messages and (messages[-1].get("role") == "assistant"):
        target_message = messages[-1]
        context_messages = messages[:-1]
    else:
        context_messages = messages

    prompt_lines: List[str] = [build_persona_header(persona_name, persona_description)]

    normalized_context: List[Dict[str, Any]] = []
    for msg in context_messages:
        normalized = normalize_plain_message(msg)
        if normalized:
            normalized_context.append(normalized)

    if normalized_context:
        windowed = apply_history_window(normalized_context, history_config)
        prompt_lines.append("История диалога:")
        for msg in windowed:
            role = msg.get("sender") or msg.get("role") or "собеседник"
            content = msg.get("content", "")
            descriptors: List[str] = []
            for label in ("emotion", "tone", "topic"):
                value = _get_field(msg, label)
                if value:
                    descriptors.append(f"{label}={value}")
            descriptor = f" ({', '.join(descriptors)})" if descriptors else ""
            prompt_lines.append(f"{role}: {content}{descriptor}".strip())
    else:
        prompt = (example.get("prompt") or "").strip()
        if prompt:
            prompt_lines.append("Контекст:")
            prompt_lines.append(prompt)

    style_hints: List[str] = []
    if target_message:
        for label, value in (
            ("эмоция", target_message.get("emotion")),
            ("тон", target_message.get("tone")),
            ("тема", target_message.get("topic")),
        ):
            if value:
                style_hints.append(f"{label} — {value}")
    if style_hints:
        prompt_lines.append("Сформируй следующую реплику, учитывая " + ", ".join(style_hints) + ".")

    prompt_text = "\n".join(line for line in prompt_lines if line).strip()
    completion_text = (
        (target_message.get("content") if target_message else None)
        or (example.get("completion") or "")
    )
    if isinstance(completion_text, list):
        fragments = []
        for block in completion_text:
            if isinstance(block, dict) and block.get("type") == "text":
                fragments.append(str(block.get("text", "")))
        completion_text = " ".join(fragments)
    completion_text = str(completion_text).strip()

    prompt_images = extract_image_refs(context_messages[-1] if context_messages else None)
    completion_images = extract_image_refs(target_message)

    return {
        "prompt": prompt_text,
        "completion": completion_text,
        "prompt_images": prompt_images,
        "completion_images": completion_images,
        "source": example.get("source"),
    }


def build_multiturn_example(
    example: Dict[str, Any],
    system_prompt: str,
    history_config: HistoryConfig,
) -> Optional[Dict[str, Any]]:
    messages: Sequence[Dict[str, Any]] = example.get("messages") or []
    if len(messages) < 2:
        return None
    if messages[-1].get("role") != "assistant":
        return None

    normalized: List[Dict[str, Any]] = []
    for msg in messages:
        normalized_msg = normalize_plain_message(msg)
        if normalized_msg:
            normalized.append(normalized_msg)

    if len(normalized) < 2:
        return None

    context = apply_history_window(normalized[:-1], history_config)
    target = normalized[-1]

    conversation: List[Dict[str, Any]] = [
        {"role": "system", "content": [make_text_block(system_prompt)]}
    ]

    for msg in context:
        chat_message = plain_to_chat_message(msg)
        if chat_message:
            conversation.append(chat_message)

    assistant_message = plain_to_chat_message(target)
    if not assistant_message:
        return None
    assistant_message["role"] = "assistant"
    conversation.append(assistant_message)

    if len(conversation) < 3:
        return None

    return {"messages": conversation, "source": example.get("source")}


def build_knowledge_prompt(
    example: Dict[str, Any],
    persona_name: str,
    persona_description: str,
) -> Dict[str, Any]:
    content = (example.get("content") or "").strip()
    if not content:
        return {}
    source = example.get("source") or example.get("document")
    prompt_lines = [
        build_persona_header(persona_name, persona_description),
        "Запомни и расскажи естественно следующий факт из твоих материалов:",
        content,
    ]
    if source:
        prompt_lines.append(f"Источник: {source}")
    prompt_lines.append("Перескажи факт от первого лица, как если бы тебя спросили об этом.")

    prompt_text = "\n".join(line for line in prompt_lines if line).strip()

    knowledge_images: List[str] = []
    for key in ("image", "image_path", "preview"):
        value = example.get(key)
        if isinstance(value, str):
            knowledge_images.append(value)
    return {
        "prompt": prompt_text,
        "completion": content,
        "prompt_images": knowledge_images,
        "completion_images": [],
        "source": source,
    }


def conversation_from_prompt(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    prompt_text = entry.get("prompt", "").strip()
    completion_text = entry.get("completion", "").strip()
    if not prompt_text or not completion_text:
        return None

    user_blocks: List[Dict[str, Any]] = []
    if prompt_text:
        user_blocks.append(make_text_block(prompt_text))
    for ref in entry.get("prompt_images", []) or []:
        user_blocks.append({"type": "image", "image": ref})

    assistant_blocks: List[Dict[str, Any]] = []
    if completion_text:
        assistant_blocks.append(make_text_block(completion_text))
    for ref in entry.get("completion_images", []) or []:
        assistant_blocks.append({"type": "image", "image": ref})

    if not user_blocks or not assistant_blocks:
        return None

    conversation = [
        {"role": "system", "content": [make_text_block(entry["system_prompt"])]},
        {"role": "user", "content": user_blocks},
        {"role": "assistant", "content": assistant_blocks},
    ]
    return {
        "messages": conversation,
        "source": entry.get("source"),
    }


def format_style_examples(
    dataset: Dataset,
    persona_name: str,
    persona_description: str,
    history_config: HistoryConfig,
) -> List[Dict[str, Any]]:
    system_prompt = build_persona_header(persona_name, persona_description)
    formatted: List[Dict[str, Any]] = []
    for example in dataset:
        multiturn = build_multiturn_example(example, system_prompt, history_config)
        if multiturn:
            formatted.append(multiturn)
            continue
        prompt_entry = build_style_prompt(
            example,
            persona_name,
            persona_description,
            history_config,
        )
        if prompt_entry:
            prompt_entry["system_prompt"] = system_prompt
            convo = conversation_from_prompt(prompt_entry)
            if convo:
                formatted.append(convo)
    return formatted


def format_knowledge_examples(
    dataset: Dataset,
    persona_name: str,
    persona_description: str,
) -> List[Dict[str, Any]]:
    system_prompt = build_persona_header(persona_name, persona_description)
    formatted: List[Dict[str, Any]] = []
    for example in dataset:
        prompt_entry = build_knowledge_prompt(example, persona_name, persona_description)
        if not prompt_entry:
            continue
        prompt_entry["system_prompt"] = system_prompt
        convo = conversation_from_prompt(prompt_entry)
        if convo:
            formatted.append(convo)
    return formatted


class ConversationDataset(TorchDataset):
    def __init__(self, conversations: Sequence[Dict[str, Any]]):
        self._data = list(conversations)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self._data[idx]


def build_data_collator(
    backend: str,
    processor: AutoProcessor,
    max_length: Optional[int],
    pad_to_multiple_of: Optional[int] = None,
) -> "BaseVLDataCollator":
    if backend == "qwen2_vl":
        return QwenVLDataCollator(
            processor=processor,
            max_length=max_length,
            pad_to_multiple_of=pad_to_multiple_of,
        )
    if backend == "glm4v":
        return GLM4VDataCollator(
            processor=processor,
            max_length=max_length,
            pad_to_multiple_of=pad_to_multiple_of,
        )
    if backend == "paligemma":
        return PaligemmaDataCollator(
            processor=processor,
            max_length=max_length,
            pad_to_multiple_of=pad_to_multiple_of,
        )
    raise ValueError(f"Неизвестный VL backend: {backend}")


class BaseVLDataCollator:
    """Marker base class for type checking."""
    pass


def render_with_template(
    processor: AutoProcessor,
    messages: Sequence[Dict[str, Any]],
    add_generation_prompt: bool,
) -> str:
    apply_template = getattr(processor, "apply_chat_template", None)
    if callable(apply_template):
        try:
            return processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=add_generation_prompt,
            )
        except ValueError:
            logger.debug("Processor has no chat template; falling back to manual rendering.")
    lines: List[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content")
        text = extract_text_from_block(content).strip()
        if not text:
            continue
        if role:
            lines.append(f"{role}: {text}")
        else:
            lines.append(text)
    if add_generation_prompt:
        lines.append("assistant:")
    return "\n".join(lines).strip()


def convert_messages_for_glm(
    messages: Sequence[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Image.Image]]:
    converted: List[Dict[str, Any]] = []
    images: List[Image.Image] = []
    for message in messages:
        role = message.get("role") or "user"
        raw_content = message.get("content")
        if not raw_content:
            prompt_text = (message.get("content") or message.get("text") or "").strip()
            raw_blocks: List[Any] = [{"type": "text", "text": prompt_text}]
        elif isinstance(raw_content, list):
            raw_blocks = list(raw_content)
        else:
            raw_blocks = [raw_content]

        new_blocks: List[Dict[str, Any]] = []
        for block in raw_blocks:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "image":
                    ref = (
                        block.get("image")
                        or block.get("url")
                        or block.get("path")
                    )
                    img = load_image_from_ref(ref)
                    if img is not None:
                        new_blocks.append({"type": "image", "image": img})
                        images.append(img)
                    continue
                if block_type == "text":
                    text = str(block.get("text") or "").strip()
                    if text:
                        new_blocks.append({"type": "text", "text": text})
                    continue
            text_value = extract_text_from_block(block).strip()
            if text_value:
                new_blocks.append({"type": "text", "text": text_value})

        if not new_blocks:
            new_blocks.append({"type": "text", "text": ""})
        converted.append({"role": role, "content": new_blocks})
    return converted, images


class QwenVLDataCollator(BaseVLDataCollator):
    def __init__(
        self,
        processor: AutoProcessor,
        max_length: Optional[int] = None,
        pad_to_multiple_of: Optional[int] = None,
    ):
        self.processor = processor
        self.max_length = max_length
        self.pad_to_multiple_of = pad_to_multiple_of
        self.supports_videos = True

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        texts: List[str] = []
        prompt_texts: List[str] = []
        image_inputs: List[Any] = []
        video_inputs: Optional[List[Any]] = [] if self.supports_videos else None

        for feature in features:
            messages = feature.get("messages")
            if not messages or len(messages) < 2:
                raise ValueError("Каждый пример должен содержать минимум system и user сообщения.")
            if messages[-1]["role"] != "assistant":
                raise ValueError("Последнее сообщение должно быть ассистента для вычисления лосса.")

            prompt_messages = messages[:-1]
            full_text = self.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
            prompt_text = self.processor.apply_chat_template(
                prompt_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            texts.append(full_text)
            prompt_texts.append(prompt_text)

            has_images = False
            has_videos = False
            for message in messages:
                content = message.get("content") or []
                if isinstance(content, dict):
                    content = [content]
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type")
                    if block_type == "image":
                        has_images = True
                    elif block_type == "video":
                        has_videos = True
                if has_images and (has_videos or not self.supports_videos):
                    break

            image_input: Any = None
            video_input: Any = None
            needs_media = has_images or (self.supports_videos and has_videos)
            if needs_media:
                image_input, video_input = process_vision_info(messages)

            image_inputs.append(image_input)
            if self.supports_videos and video_inputs is not None:
                video_inputs.append(video_input)

        images_arg: Optional[List[Any]]
        videos_arg: Optional[List[Any]]

        if any(item is not None for item in image_inputs):
            images_arg = [
                sample if sample is not None else []
                for sample in image_inputs
            ]
        else:
            images_arg = None

        if self.supports_videos and video_inputs is not None and any(
            item is not None for item in video_inputs
        ):
            videos_arg = [
                sample if sample is not None else []
                for sample in video_inputs
            ]
        else:
            videos_arg = None

        processor_kwargs: Dict[str, Any] = {
            "text": texts,
            "padding": True,
            "max_length": self.max_length,
            "pad_to_multiple_of": self.pad_to_multiple_of,
            "return_tensors": "pt",
        }
        if images_arg is not None:
            processor_kwargs["images"] = images_arg
        if videos_arg is not None:
            processor_kwargs["videos"] = videos_arg

        batch = self.processor(**processor_kwargs)

        labels = batch["input_ids"].clone()
        for idx, prompt_text in enumerate(prompt_texts):
            prompt_ids = self.processor.tokenizer(
                prompt_text,
                add_special_tokens=False,
            )["input_ids"]
            prompt_length = min(len(prompt_ids), labels.shape[1])
            labels[idx, :prompt_length] = -100
        labels[batch["attention_mask"] == 0] = -100
        batch["labels"] = labels
        return batch


class PaligemmaDataCollator(BaseVLDataCollator):
    def __init__(
        self,
        processor: AutoProcessor,
        max_length: Optional[int] = None,
        pad_to_multiple_of: Optional[int] = None,
    ):
        self.processor = processor
        self.max_length = max_length
        self.pad_to_multiple_of = pad_to_multiple_of
        self._warned_images = False

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        texts: List[str] = []
        prompt_texts: List[str] = []
        batch_images: List[Image.Image] = []
        missing_images = False

        for feature in features:
            messages = feature.get("messages")
            if not messages or len(messages) < 2:
                raise ValueError("Каждый пример должен содержать минимум system и user сообщения.")
            if messages[-1]["role"] != "assistant":
                raise ValueError("Последнее сообщение должно быть ассистента для вычисления лосса.")
            full_text = render_with_template(self.processor, messages, add_generation_prompt=False)
            prompt_messages = messages[:-1] if len(messages) > 1 else messages
            prompt_text = render_with_template(self.processor, prompt_messages, add_generation_prompt=True)
            texts.append(full_text)
            prompt_texts.append(prompt_text)

            sample_refs: List[str] = []
            for message in messages:
                sample_refs.extend(extract_image_refs(message))
            sample_image: Optional[Image.Image] = None
            for ref in sample_refs:
                sample_image = load_image_from_ref(ref)
                if sample_image is not None:
                    break
            if sample_image is None:
                missing_images = True
                sample_image = create_dummy_image()
            batch_images.append(sample_image)

        if missing_images and not self._warned_images:
            logger.warning(
                "PaligemmaDataCollator не нашёл изображения в части примеров — использую заглушку 448x448."
            )
            self._warned_images = True

        processor_kwargs: Dict[str, Any] = {
            "text": texts,
            "padding": True,
            "return_tensors": "pt",
        }
        if self.max_length is not None:
            processor_kwargs["max_length"] = self.max_length
        if self.pad_to_multiple_of is not None:
            processor_kwargs["pad_to_multiple_of"] = self.pad_to_multiple_of
        processor_kwargs["images"] = batch_images

        batch = self.processor(**processor_kwargs)
        if not hasattr(self.processor, "tokenizer") or self.processor.tokenizer is None:
            raise ValueError("Paligemma processor не содержит tokenizer для маскирования меток.")

        labels = batch["input_ids"].clone()
        for idx, prompt_text in enumerate(prompt_texts):
            prompt_ids = self.processor.tokenizer(
                prompt_text,
                add_special_tokens=False,
            )["input_ids"]
            prompt_len = min(len(prompt_ids), labels.shape[1])
            labels[idx, :prompt_len] = -100
        attention_mask = batch.get("attention_mask")
        if attention_mask is not None:
            labels[attention_mask == 0] = -100
        batch["labels"] = labels
        return batch


class GLM4VDataCollator(BaseVLDataCollator):
    def __init__(
        self,
        processor: AutoProcessor,
        max_length: Optional[int] = None,
        pad_to_multiple_of: Optional[int] = None,
    ):
        self.processor = processor
        self.max_length = max_length
        self.pad_to_multiple_of = pad_to_multiple_of
        tokenizer = getattr(processor, "tokenizer", None)
        if tokenizer is None:
            raise ValueError("AutoProcessor для GLM должен иметь tokenizer.")
        if getattr(tokenizer, "pad_token_id", None) is None:
            if getattr(tokenizer, "eos_token_id", None) is None:
                raise ValueError("Tokenizer должен иметь pad_token_id или eos_token_id.")
            tokenizer.pad_token_id = tokenizer.eos_token_id
        self.tokenizer = tokenizer
        self.pad_token_id = tokenizer.pad_token_id

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        batch_messages: List[List[Dict[str, Any]]] = []
        batch_prompt_messages: List[List[Dict[str, Any]]] = []
        batch_images: List[List[Image.Image]] = []

        for feature in features:
            messages = feature.get("messages")
            if not messages or len(messages) < 2:
                raise ValueError("Каждый пример должен содержать минимум system и user сообщения.")
            if messages[-1]["role"] != "assistant":
                raise ValueError("Последнее сообщение должно быть ассистента для вычисления лосса.")
            converted, images = convert_messages_for_glm(messages)
            prompt_converted = converted[:-1] if len(converted) > 1 else converted
            batch_messages.append(converted)
            batch_prompt_messages.append(prompt_converted)
            batch_images.append(images)

        full_texts: List[str] = []
        prompt_texts: List[str] = []
        for converted, prompt_converted in zip(batch_messages, batch_prompt_messages):
            full_texts.append(
                self.processor.apply_chat_template(
                    converted,
                    tokenize=False,
                    add_generation_prompt=False,
                )
            )
            prompt_texts.append(
                self.processor.apply_chat_template(
                    prompt_converted,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            )

        processor_kwargs: Dict[str, Any] = {
            "text": full_texts,
            "padding": True,
            "return_tensors": "pt",
        }
        if self.max_length is not None:
            processor_kwargs["max_length"] = self.max_length
        if self.pad_to_multiple_of is not None:
            processor_kwargs["pad_to_multiple_of"] = self.pad_to_multiple_of
        if any(images for images in batch_images):
            processor_kwargs["images"] = batch_images

        outputs = self.processor(**processor_kwargs)
        batch = {key: value for key, value in outputs.items()}

        if "labels" not in batch:
            labels = batch["input_ids"].clone()
            for idx, prompt_text in enumerate(prompt_texts):
                prompt_ids = self.tokenizer(
                    prompt_text,
                    add_special_tokens=False,
                )["input_ids"]
                prompt_len = min(len(prompt_ids), labels.shape[1])
                labels[idx, :prompt_len] = -100
            attention = batch.get("attention_mask")
            if attention is not None:
                labels[attention == 0] = -100
            else:
                labels[labels == self.pad_token_id] = -100
            batch["labels"] = labels

        return batch


class GLMTrainer(Trainer):
    def compute_loss(
        self,
        model,
        inputs,
        num_items_in_batch: Optional[int] = None,
        return_outputs: bool = False,
    ):
        outputs = model(**inputs)
        loss: Optional[torch.Tensor]
        if isinstance(outputs, dict):
            loss = outputs.get("loss")
        elif hasattr(outputs, "loss"):
            loss = outputs.loss
        else:
            loss = outputs[0]
        if loss is None:
            raise ValueError("GLM модель не вернула loss.")
        return (loss, outputs) if return_outputs else loss


def maybe_enable_tf32(enable: bool) -> None:
    if enable and torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True


def build_quant_config() -> BitsAndBytesConfig:
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )


def build_lora_config(args: argparse.Namespace) -> LoraConfig:
    return LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=args.target_modules,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )


def save_training_config(args: argparse.Namespace, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / "training_args.json"
    with config_path.open("w", encoding="utf-8") as fh:
        json.dump(vars(args), fh, indent=2, ensure_ascii=False)


def prepare_datasets(
    args: argparse.Namespace,
    style_train_raw: Dataset,
    style_eval_raw: Dataset,
    knowledge_raw: Optional[Dataset],
    history_config: HistoryConfig,
) -> tuple[ConversationDataset, ConversationDataset]:
    train_examples = format_style_examples(
        style_train_raw,
        persona_name=args.persona_name,
        persona_description=args.persona_description,
        history_config=history_config,
    )
    eval_examples = format_style_examples(
        style_eval_raw,
        persona_name=args.persona_name,
        persona_description=args.persona_description,
        history_config=history_config,
    )

    if knowledge_raw is not None:
        knowledge_examples = format_knowledge_examples(
            knowledge_raw,
            persona_name=args.persona_name,
            persona_description=args.persona_description,
        )
        repeated = knowledge_examples * max(1, args.knowledge_repeat)
        train_examples.extend(repeated)

    rng = random.Random(args.seed)
    rng.shuffle(train_examples)

    if args.max_train_samples is not None:
        train_examples = train_examples[: args.max_train_samples]
    if args.max_eval_samples is not None:
        eval_examples = eval_examples[: args.max_eval_samples]

    return ConversationDataset(train_examples), ConversationDataset(eval_examples)


def run_training(args: argparse.Namespace) -> TrainingRunResult:
    configure_logging(args.log_level)
    # Если пользователь указал явный системный промт, используем его как persona_description
    if getattr(args, "system_prompt", None):
        args.persona_description = args.system_prompt
        logger.info("Используем system_prompt как persona_description (%d символов).", len(args.system_prompt))
    backend_name = infer_backend(args.model_id, args.vl_backend)
    args.vl_backend = backend_name
    logger.info("Запускаю тренировку QLoRA для модели %s (backend=%s)", args.model_id, backend_name)

    maybe_enable_tf32(args.tf32)

    if not torch.cuda.is_available():
        raise SystemError("Для QLoRA требуется GPU с поддержкой CUDA.")

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)

    train_path = Path(args.train_file)
    eval_path = Path(args.eval_file)
    knowledge_path = Path(args.knowledge_file)
    ensure_file(train_path, "Train split")
    ensure_file(eval_path, "Eval split")

    style_train_raw = load_json_dataset(train_path)
    style_eval_raw = load_json_dataset(eval_path)
    knowledge_raw = load_optional_dataset(knowledge_path)

    processor_id = args.processor_id or args.model_id
    processor = AutoProcessor.from_pretrained(
        processor_id,
        trust_remote_code=args.trust_remote_code,
    )
    if hasattr(processor, "tokenizer") and processor.tokenizer is not None:
        tokenizer = processor.tokenizer
        if getattr(tokenizer, "pad_token_id", None) is None and getattr(tokenizer, "eos_token_id", None) is not None:
            tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.padding_side = "right"

    history_config = HistoryConfig(
        max_history_turns=max(2, args.max_history_turns),
        summary_max_chars=max(120, args.history_summary_max_chars),
    )

    train_dataset, eval_dataset = prepare_datasets(
        args,
        style_train_raw,
        style_eval_raw,
        knowledge_raw,
        history_config,
    )
    if len(train_dataset) == 0:
        raise RuntimeError("Обучающий датасет пуст — нечего тренировать.")
    if len(eval_dataset) == 0:
        logger.warning("Eval датасет пуст — метрики по валидации недоступны.")

    data_collator = build_data_collator(
        backend_name,
        processor=processor,
        max_length=args.max_seq_length,
    )

    quant_config = build_quant_config()
    if backend_name == "qwen2_vl":
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            args.model_id,
            device_map="auto",
            quantization_config=quant_config,
            trust_remote_code=args.trust_remote_code,
        )
    elif backend_name == "glm4v":
        model = Glm4vForConditionalGeneration.from_pretrained(
            args.model_id,
            device_map="auto",
            quantization_config=quant_config,
            trust_remote_code=args.trust_remote_code,
        )
    else:
        model = PaliGemmaForConditionalGeneration.from_pretrained(
            args.model_id,
            device_map="auto",
            quantization_config=quant_config,
            trust_remote_code=args.trust_remote_code,
        )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, build_lora_config(args))
    if hasattr(model, "config") and hasattr(model.config, "use_cache"):
        model.config.use_cache = False
    model.gradient_checkpointing_enable()

    training_kwargs = dict(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.eval_batch_size or args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        logging_steps=max(1, args.logging_steps),
        save_total_limit=2,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        report_to="tensorboard",
        dataloader_num_workers=max(0, args.dataloader_num_workers),
        remove_unused_columns=False,
    )

    fields = TrainingArguments.__dataclass_fields__
    if "logging_strategy" in fields:
        training_kwargs["logging_strategy"] = IntervalStrategy.STEPS if IntervalStrategy else "steps"
    if "save_steps" in fields:
        training_kwargs["save_steps"] = args.save_steps
    if "save_strategy" in fields:
        training_kwargs["save_strategy"] = SaveStrategy.STEPS if SaveStrategy else "steps"
    if "eval_steps" in fields:
        training_kwargs["eval_steps"] = args.eval_steps
    if "evaluation_strategy" in fields:
        training_kwargs["evaluation_strategy"] = IntervalStrategy.STEPS if IntervalStrategy else "steps"
    elif "eval_strategy" in fields:
        training_kwargs["eval_strategy"] = IntervalStrategy.STEPS if IntervalStrategy else "steps"
    if "load_best_model_at_end" in fields:
        training_kwargs["load_best_model_at_end"] = False
    if "metric_for_best_model" in fields:
        training_kwargs["metric_for_best_model"] = "eval_loss"
    if "greater_is_better" in fields:
        training_kwargs["greater_is_better"] = False
    if args.bf16 and "bf16" in fields:
        training_kwargs["bf16"] = True
    elif "fp16" in fields:
        training_kwargs["fp16"] = True

    training_args = TrainingArguments(**training_kwargs)

    callbacks = []
    if EarlyStoppingCallback is not None and args.early_stopping_patience > 0:
        callbacks.append(EarlyStoppingCallback(early_stopping_patience=args.early_stopping_patience))

    trainer_class = Trainer if backend_name != "glm4v" else GLMTrainer
    trainer = trainer_class(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset if len(eval_dataset) > 0 else None,
        data_collator=data_collator,
        tokenizer=processor.tokenizer if hasattr(processor, "tokenizer") else None,
        callbacks=callbacks or None,
    )

    train_result = trainer.train()
    trainer.log_metrics("train", train_result.metrics)
    trainer.save_metrics("train", train_result.metrics)
    trainer.save_state()

    adapter_dir = Path(args.adapter_dir)
    trainer.model.save_pretrained(adapter_dir)
    processor.save_pretrained(adapter_dir)
    save_training_config(args, adapter_dir)
    logger.info("LoRA адаптер сохранён в %s", adapter_dir)

    return TrainingRunResult(
        adapter_dir=adapter_dir,
        output_dir=Path(args.output_dir),
        train_metrics=dict(train_result.metrics),
    )


def main() -> None:
    args = parse_args()
    result = run_training(args)
    print(f"Adapter saved to {result.adapter_dir}")


if __name__ == "__main__":
    main()
