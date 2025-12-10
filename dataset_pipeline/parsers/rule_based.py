from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from dataset_pipeline.core.schemas import ParsedDocument, ParsedMessage
from dataset_pipeline.core.utils import merge_metadata, normalise_whitespace, parse_russian_datetime, safe_read_text

logger = logging.getLogger(__name__)


TXT_PATTERNS = [
    re.compile(r"^\[(?P<datetime>[\d./,: ]+)\]\s+(?P<sender>[^:]+):\s*(?P<content>.+)$"),
    re.compile(
        r"^(?P<date>\d{2}\.\d{2}\.\d{4}), (?P<time>\d{2}:\d{2}(?::\d{2})?) (?P<sender>[^ ]+)\s+(?P<content>.+)$"
    ),
    re.compile(r"^(?P<sender>[^:]+):\s*(?P<content>.+)$"),
]


class RuleBasedParser:
    """Parses structured chat exports (TXT/HTML/JSON/JSONL)."""

    TXT_EXTENSIONS = {".txt", ".log", ".csv"}
    HTML_EXTENSIONS = {".html", ".htm"}
    JSON_EXTENSIONS = {".json", ".jsonl"}

    def parse(self, path: Path) -> Optional[ParsedDocument]:
        suffix = path.suffix.lower()
        if suffix in self.TXT_EXTENSIONS:
            text = safe_read_text(path)
            raw_messages = self._parse_txt_dialog(text)
            format_hint = suffix.lstrip(".") or "txt"
        elif suffix in self.HTML_EXTENSIONS:
            raw_messages = self._parse_html_dialog(path)
            format_hint = "html"
        elif suffix == ".json":
            raw_messages = self._parse_json_dialog(path)
            format_hint = "json"
        elif suffix == ".jsonl":
            raw_messages = self._parse_jsonl_dialog(path)
            format_hint = "jsonl"
        else:
            logger.debug("RuleBasedParser: unsupported format %s", path)
            return None

        return self._build_document(
            raw_messages=raw_messages,
            source=path,
            parser_type="rule_based",
            format_hint=format_hint,
        )

    def parse_text(
        self,
        text: str,
        source: Path,
        parser_type: str = "rule_based",
        format_hint: str = "txt",
    ) -> Optional[ParsedDocument]:
        """Expose TXT parser for OCR/hybrid pipelines."""
        raw_messages = self._parse_txt_dialog(text)
        if not raw_messages:
            return None
        return self._build_document(
            raw_messages=raw_messages,
            source=source,
            parser_type=parser_type,
            format_hint=format_hint,
        )

    def _build_document(
        self,
        raw_messages: List[Dict],
        source: Path,
        parser_type: str,
        format_hint: str,
    ) -> Optional[ParsedDocument]:
        if not raw_messages:
            logger.debug("RuleBasedParser: no messages in %s", source)
            return None

        parsed: List[ParsedMessage] = []
        for order, raw in enumerate(raw_messages):
            text = normalise_whitespace(str(raw.get("content") or ""))
            if not text:
                continue
            metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
            metadata = merge_metadata(metadata, {"order": order})
            timestamp_raw = raw.get("timestamp")
            timestamp = parse_russian_datetime(timestamp_raw) if isinstance(timestamp_raw, str) else None
            role = raw.get("role")
            if role not in {"user", "assistant", "system"}:
                role = None
            parsed.append(
                ParsedMessage(
                    role=role,  # type: ignore[arg-type]
                    content=text,
                    sender=(raw.get("sender") or raw.get("name") or raw.get("from")) or None,
                    timestamp=timestamp,
                    metadata=metadata,
                )
            )

        if not parsed:
            logger.debug("RuleBasedParser: filtered all messages from %s", source)
            return None

        return ParsedDocument(
            source=str(source),
            doc_type="dialogue",
            parser_type=parser_type,
            format=format_hint,
            messages=parsed,
            metadata={"parser_type": parser_type, "format": format_hint},
        )

    def _parse_txt_dialog(self, text: str) -> List[Dict]:
        lines = [line.strip() for line in text.splitlines()]
        messages: List[Dict] = []

        for line in lines:
            if not line:
                continue
            matched = None
            for pattern in TXT_PATTERNS:
                matched = pattern.match(line)
                if matched:
                    break
            if matched:
                timestamp_raw = self._build_timestamp(matched)
                messages.append(
                    {
                        "timestamp": timestamp_raw,
                        "sender": matched.group("sender").strip(),
                        "content": matched.group("content").strip(),
                    }
                )
            elif messages:
                messages[-1]["content"] = normalise_whitespace(messages[-1]["content"] + f"\n{line}")
        return messages

    def _build_timestamp(self, match: re.Match) -> Optional[str]:
        if "datetime" in match.groupdict():
            return match.group("datetime")
        if "date" in match.groupdict() and "time" in match.groupdict():
            return f"{match.group('date')}, {match.group('time')}"
        return None

    def _parse_html_dialog(self, path: Path) -> List[Dict]:
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except ImportError:  # pragma: no cover - optional dependency
            logger.warning("BeautifulSoup not installed; cannot parse %s", path)
            return []

        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        messages: List[Dict] = []
        for msg in soup.select(".message"):
            sender = msg.select_one(".from_name")
            text = msg.select_one(".text")
            time = msg.select_one(".date")
            if not text:
                continue
            messages.append(
                {
                    "timestamp": time["title"] if time and time.has_attr("title") else None,
                    "sender": sender.get_text(strip=True) if sender else None,
                    "content": text.get_text(separator="\n", strip=True),
                }
            )
        return messages

    def _parse_json_dialog(self, path: Path) -> List[Dict]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError:
            logger.debug("Fallback to JSONL parser for %s", path)
            return self._parse_jsonl_dialog(path)

        messages = self._parse_structured_records(data, path)
        if messages:
            return messages

        logger.debug("No messages extracted from %s (JSON).", path)
        return []

    def _parse_jsonl_dialog(self, path: Path) -> List[Dict]:
        messages: List[Dict] = []
        with path.open("r", encoding="utf-8") as fh:
            for index, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping malformed JSONL line %s in %s: %s", index + 1, path, exc)
                    continue
                if not isinstance(record, dict):
                    continue
                structured = self._structured_record_to_messages(record, path, index)
                if structured:
                    messages.extend(structured)
        return messages

    def _structured_record_to_messages(self, record: Dict, source: Path, index: int) -> List[Dict]:
        messages: List[Dict] = []
        seq = record.get("messages")
        if not isinstance(seq, list):
            return messages

        base_metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        chat_key = self._derive_chat_key(base_metadata, source, index)
        base_metadata = merge_metadata(base_metadata, {"chat_id": chat_key})

        for order, raw in enumerate(seq):
            if not isinstance(raw, dict):
                continue
            content = raw.get("content")
            if not isinstance(content, str):
                continue
            text = normalise_whitespace(content)
            if not text:
                continue
            raw_metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
            metadata = merge_metadata(base_metadata, raw_metadata)
            metadata.setdefault("order", raw.get("order", order))
            messages.append(
                {
                    "timestamp": raw.get("timestamp"),
                    "sender": raw.get("sender") or raw.get("name") or raw.get("role"),
                    "role": raw.get("role"),
                    "content": text,
                    "metadata": metadata,
                }
            )

        completion = record.get("completion")
        if isinstance(completion, str):
            completion_text = normalise_whitespace(completion)
            if completion_text and (not messages or messages[-1].get("content") != completion_text):
                completion_meta = merge_metadata(
                    base_metadata, {"order": len(messages), "source": "completion"}
                )
                messages.append(
                    {
                        "timestamp": None,
                        "sender": base_metadata.get("assistant_sender") or "assistant",
                        "role": "assistant",
                        "content": completion_text,
                        "metadata": completion_meta,
                    }
                )
        return messages

    def _parse_structured_records(self, payload, source: Path) -> List[Dict]:
        records: List[Dict] = []
        if isinstance(payload, dict) and any(key in payload for key in ("messages", "prompt", "completion")):
            structured = self._structured_record_to_messages(payload, source, 0)
            records.extend(structured)
        elif isinstance(payload, list):
            for idx, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                if not any(key in item for key in ("messages", "prompt", "completion")):
                    continue
                structured = self._structured_record_to_messages(item, source, idx)
                records.extend(structured)
        return records

    def _derive_chat_key(self, metadata: Dict, source: Path, index: int) -> str:
        if metadata:
            for field in ("chat_id", "dialog_id", "dialogue_id", "conversation_id", "id"):
                value = metadata.get(field)
                if value:
                    return str(value)
        return f"{source.stem}_{index}"
