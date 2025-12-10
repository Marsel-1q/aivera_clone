from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup  # type: ignore
from openai import OpenAI

# Позволяем импортировать config.py, даже если есть одноимённый модуль в корне репо.
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import Config, ROLE_INSTRUCTIONS, SYSTEM_PROMPT_TEMPLATE  # noqa: E402

logger = logging.getLogger("syntetic-dialog")

INTERMEDIATE_SAVE_EVERY = 10

# ---------- Data structures -------------------------------------------------


@dataclass
class DialogueExample:
    """Хранилище примера для промпта."""

    source: str
    content: str

    def trimmed(self, max_lines: int = 80) -> str:
        lines = [line.strip() for line in self.content.splitlines() if line.strip()]
        return "\n".join(lines[:max_lines])


# ---------- Data loader -----------------------------------------------------


class DataLoader:
    """Читает примеры из data/raw для подсказок LLM."""

    SUPPORTED_EXTENSIONS = {".html", ".htm", ".jsonl", ".json", ".txt", ".md"}

    def __init__(self, raw_path: Path):
        self.raw_path = raw_path

    def load_examples(self, limit: int) -> List[DialogueExample]:
        examples: List[DialogueExample] = []
        if not self.raw_path.exists():
            logger.warning("Папка с примерами %s не найдена", self.raw_path)
            return examples

        for file_path in sorted(self.raw_path.rglob("*")):
            if len(examples) >= limit:
                break
            if not file_path.is_file() or file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue

            try:
                example = self._parse_file(file_path)
            except Exception as exc:  # pragma: no cover - лог для отладки
                logger.debug("Не удалось распарсить %s: %s", file_path, exc)
                continue

            if example:
                examples.append(example)

        return examples

    def _parse_file(self, file_path: Path) -> Optional[DialogueExample]:
        suffix = file_path.suffix.lower()
        if suffix in {".html", ".htm"}:
            return self._parse_html_dialogue(file_path)
        if suffix in {".jsonl", ".json"}:
            return self._parse_textual_dialogue(file_path)
        return self._parse_textual_dialogue(file_path)

    def _parse_html_dialogue(self, file_path: Path) -> Optional[DialogueExample]:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(text, "html.parser")
        segments: List[str] = []

        for message in soup.select("div.message"):
            if "service" in message.get("class", []):
                continue
            payload = message.select_one("div.text")
            if payload is None:
                continue
            speaker_node = message.select_one("div.from_name")
            speaker = speaker_node.get_text(" ", strip=True) if speaker_node else ""
            content = payload.get_text("\n", strip=True)
            if not content:
                continue
            if not speaker:
                speaker = "user" if len(segments) % 2 == 0 else "assistant"
            segments.append(f"{speaker}: {content}")

        dialogue = "\n".join(segments).strip()
        if not dialogue:
            return None
        return DialogueExample(source=file_path.name, content=dialogue)

    def _parse_textual_dialogue(self, file_path: Path) -> Optional[DialogueExample]:
        content = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            return None
        return DialogueExample(source=file_path.name, content=content)


# ---------- Prompt builder --------------------------------------------------


class PromptBuilder:
    def __init__(self, min_messages: int):
        self.min_messages = min_messages

    def build(
        self,
        role: str,
        role_instruction_override: Optional[str],
        example: Optional[DialogueExample],
    ) -> str:
        role_instruction = (
            role_instruction_override
            or ROLE_INSTRUCTIONS.get(role)
            or "Поддерживай профессиональный, дружелюбный тон и глубоко отвечай на вопросы."
        )
        example_block = example.trimmed() if example else "Примеры отсутствуют, руководствуйся требованиями."
        return SYSTEM_PROMPT_TEMPLATE.format(
            role_title=role.replace("_", " ").title(),
            role_type=role,
            min_messages=self.min_messages,
            role_instruction=role_instruction,
            example_dialogue=example_block,
        )


# ---------- Dialogue generator ---------------------------------------------


class DialogueGenerator:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    def generate(self, system_prompt: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": "Сгенерируй новый диалог и верни JSON как описано выше.",
                    },
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"},
                timeout=self.config.request_timeout,
            )
        except Exception as exc:  # pragma: no cover - сетевые ошибки
            logger.error("Ошибка вызова модели: %s", exc)
            return None

        content = response.choices[0].message.content.strip()
        payload = self._extract_json_block(content)
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            logger.warning("Не удалось распарсить JSON: %s\n%s", exc, payload[:500])
            return None

    @staticmethod
    def _extract_json_block(text: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text


# ---------- Validator & normalizer -----------------------------------------


class DialogueValidator:
    def __init__(self, min_messages: int):
        self.min_messages = min_messages

    def validate(self, dialogue: Optional[Dict[str, Any]]) -> List[str]:
        errors: List[str] = []
        if not isinstance(dialogue, dict):
            return ["Ответ не является JSON-объектом."]

        prompt = dialogue.get("prompt")
        completion = dialogue.get("completion")
        messages = dialogue.get("messages")

        if not isinstance(prompt, str) or len(prompt.strip()) < 50:
            errors.append("prompt пустой или слишком короткий.")
        if not isinstance(completion, str) or len(completion.strip()) < 10:
            errors.append("completion пустой или слишком короткий.")
        if not isinstance(messages, list):
            errors.append("messages должен быть массивом.")
        else:
            cleaned_messages = [m for m in messages if isinstance(m, dict) and m.get("content")]
            if len(cleaned_messages) < self.min_messages:
                errors.append(f"messages содержит меньше {self.min_messages} элементов.")
            roles = {m.get("role", "").lower() for m in cleaned_messages}
            if not {"user", "assistant"} <= roles:
                errors.append("messages должен содержать роли user и assistant.")

        return errors


class DataNormalizer:
    def __init__(self, role: str):
        self.role = role

    def normalize(self, dialogue: Dict[str, Any]) -> Dict[str, Any]:
        normalized_prompt = self._clean_multiline(dialogue.get("prompt", ""))
        normalized_completion = self._clean_single_line(dialogue.get("completion", ""))
        normalized_messages = self._normalize_messages(dialogue.get("messages", []))
        metadata = dict(dialogue.get("metadata") or {})
        metadata.update(
            {
                "role_type": self.role,
                "generated": True,
                "source": "syntetic-dialog",
            }
        )
        return {
            "prompt": normalized_prompt,
            "completion": normalized_completion,
            "messages": normalized_messages,
            "metadata": metadata,
        }

    @staticmethod
    def _clean_multiline(text: str) -> str:
        lines = [line.strip() for line in (text or "").splitlines()]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _clean_single_line(text: str) -> str:
        return " ".join((text or "").split()).strip()

    def _normalize_messages(self, messages: Any) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        if not isinstance(messages, list):
            return normalized
        for idx, message in enumerate(messages):
            if not isinstance(message, dict):
                continue
            content = self._clean_single_line(message.get("content", ""))
            if not content:
                continue
            role = (message.get("role") or "user").lower()
            order = int(message.get("order", idx))
            normalized.append({"role": role, "content": content, "order": order})
        normalized.sort(key=lambda item: item["order"])
        for idx, message in enumerate(normalized):
            message["order"] = idx
        return normalized


# ---------- Helpers --------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Генерация синтетических диалогов через OpenAI-совместимое API (по умолчанию GPT-4o mini)."
    )
    parser.add_argument("--role", help="Код роли (по умолчанию из окружения).")
    parser.add_argument("--role-instruction", help="Переопределить instruction для роли.")
    parser.add_argument("--count", type=int, help="Сколько диалогов сгенерировать.")
    parser.add_argument("--min-messages", type=int, help="Минимальное число сообщений в messages.")
    parser.add_argument("--example-limit", type=int, help="Сколько примеров подмешивать в промпт.")
    parser.add_argument("--raw-data-path", type=Path, help="Путь к каталогу с реальными примерами.")
    parser.add_argument("--output", type=Path, help="Каталог для сохранения jsonl.")
    parser.add_argument(
        "--base-url",
        help="Базовый URL OpenAI-совместимого API (по умолчанию https://api.openai.com/v1).",
    )
    parser.add_argument("--model", help="Имя модели (по умолчанию gpt-4o-mini).")
    parser.add_argument("--temperature", type=float, help="Температура выборки.")
    parser.add_argument("--max-tokens", type=int, help="Максимум токенов ответа.")
    parser.add_argument("--sleep", type=float, help="Пауза между запросами (сек).")
    parser.add_argument("--max-retries", type=int, help="Сколько раз повторять генерацию при неудаче.")
    parser.add_argument("--log-level", default="INFO", help="Уровень логирования (DEBUG, INFO, ...).")
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def save_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for item in items:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")


def save_report(path: Path, stats: Dict[str, Any], config: Config, examples: List[DialogueExample]) -> None:
    report = {
        "stats": stats,
        "config": asdict(config),
        "examples_used": [example.source for example in examples],
        "generated_at": datetime.utcnow().isoformat(),
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)

    base_config = Config.from_env()
    config = base_config.with_overrides(
        role=args.role,
        num_conversations=args.count,
        min_messages=args.min_messages,
        example_limit=args.example_limit,
        raw_data_path=args.raw_data_path,
        output_path=args.output,
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        sleep_between_requests=args.sleep,
        max_retries=args.max_retries,
    )

    if not config.api_key:
        logger.error("OPENAI_API_KEY не задан. Установите ключ API и повторите запуск.")
        raise SystemExit(1)

    config.output_path.mkdir(parents=True, exist_ok=True)

    loader = DataLoader(config.raw_data_path)
    examples = loader.load_examples(config.example_limit)
    prompt_builder = PromptBuilder(config.min_messages)
    generator = DialogueGenerator(config)
    validator = DialogueValidator(config.min_messages)
    normalizer = DataNormalizer(config.role)

    stats: Dict[str, Any] = {
        "requested": config.num_conversations,
        "generated": 0,
        "failed_calls": 0,
        "invalid": 0,
        "min_messages": config.min_messages,
        "role": config.role,
        "started_at": datetime.utcnow().isoformat(),
    }

    dialogues: List[Dict[str, Any]] = []
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_file = config.output_path / f"synthetic_{config.role}_{timestamp}.jsonl"

    for idx in range(config.num_conversations):
        example = random.choice(examples) if examples else None
        system_prompt = prompt_builder.build(config.role, args.role_instruction, example)

        logger.info("Генерация диалога %s/%s...", idx + 1, config.num_conversations)
        success = False
        for attempt in range(1, config.max_retries + 1):
            logger.debug("Попытка %s для диалога %s", attempt, idx + 1)
            dialogue = generator.generate(system_prompt)
            if dialogue is None:
                stats["failed_calls"] += 1
                time.sleep(config.sleep_between_requests)
                continue

            errors = validator.validate(dialogue)
            if errors:
                stats["invalid"] += 1
                logger.warning("Валидация провалена: %s", "; ".join(errors))
                time.sleep(config.sleep_between_requests)
                continue

            normalized = normalizer.normalize(dialogue)
            dialogues.append(normalized)
            stats["generated"] += 1
            if len(dialogues) % INTERMEDIATE_SAVE_EVERY == 0:
                save_jsonl(output_file, dialogues)
                logger.info("Промежуточное сохранение %s диалогов в %s", len(dialogues), output_file)
            success = True
            break

        if not success:
            logger.error("Не удалось получить валидный диалог #%s", idx + 1)

        time.sleep(config.sleep_between_requests)

    stats["finished_at"] = datetime.utcnow().isoformat()
    stats["success_rate"] = round(
        (stats["generated"] / config.num_conversations) if config.num_conversations else 0, 3
    )

    report_file = output_file.with_suffix(".report.json")

    if dialogues:
        save_jsonl(output_file, dialogues)
        save_report(report_file, stats, config, examples)
        logger.info("Сохранено %s диалогов в %s", len(dialogues), output_file)
        logger.info("Отчёт: %s", report_file)
    else:
        logger.warning("Не удалось сгенерировать ни одного диалога. Отчёт сохранён для отладки.")
        save_report(report_file, stats, config, examples)


if __name__ == "__main__":
    main()
