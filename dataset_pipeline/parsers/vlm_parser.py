from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PIL import Image

from dataset_pipeline.core.schemas import ParsedDocument
from dataset_pipeline.core.utils import merge_metadata, normalise_whitespace

from .rule_based import RuleBasedParser

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "Расшифруй весь текст на изображении. Сохрани структуру диалога, если она есть."
)


class VLMParser:
    """Wrapper around Qwen2-VL OCR (HF pipeline)."""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".heic"}

    def __init__(
        self,
        model_id: str = "prithivMLmods/Qwen2-VL-OCR-2B-Instruct",
        enable: bool = True,
        rule_parser: Optional[RuleBasedParser] = None,
        prompt: str = DEFAULT_PROMPT,
        device: str | int | None = None,
    ) -> None:
        self.model_id = model_id
        self.enable = enable
        self.rule_parser = rule_parser
        self.prompt = prompt
        self.device = device
        self._pipeline = None

    def _ensure_pipeline(self) -> None:
        if not self.enable or self._pipeline is not None:
            return
        try:
            from transformers import pipeline as hf_pipeline  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            logger.warning("Transformers not installed, disabling VLM parser: %s", exc)
            self.enable = False
            return
        try:
            kwargs = {"model": self.model_id}
            if self.device is not None:
                kwargs["device_map"] = self.device
            logger.info("Loading Qwen2-VL OCR pipeline: %s", self.model_id)
            self._pipeline = hf_pipeline("image-text-to-text", **kwargs)
        except Exception as exc:  # pragma: no cover - runtime failure
            logger.warning("Failed to initialise Qwen OCR pipeline: %s", exc)
            self.enable = False
            self._pipeline = None

    def parse(self, path: Path, doc_type: str) -> Optional[ParsedDocument]:
        if not self.enable:
            return None
        self._ensure_pipeline()
        if self._pipeline is None:
            return None

        text = self._extract_text(path)
        if not text:
            return None
        cleaned = normalise_whitespace(text)
        if not cleaned:
            return None

        metadata = {"parser_type": "vlm", "model_id": self.model_id, "raw_text": cleaned}

        if doc_type == "dialogue" and self.rule_parser:
            logger.debug("Routing OCR text from %s to rule-based parser.", path)
            doc = self.rule_parser.parse_text(cleaned, path, parser_type="vlm", format_hint="ocr")
            if doc:
                merged_meta = merge_metadata(doc.metadata, metadata)
                return doc.copy(update={"metadata": merged_meta, "parser_type": "vlm"})

        return ParsedDocument(
            source=str(path),
            doc_type="knowledge",
            parser_type="vlm",
            format=path.suffix.lstrip(".") or "image",
            knowledge=cleaned,
            metadata=metadata,
        )

    def _extract_text(self, path: Path) -> str:
        image = self._load_image(path)
        if image is None or self._pipeline is None:
            return ""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": self.prompt},
                ],
            }
        ]
        try:
            logger.debug("Running Qwen OCR on %s", path)
            result = self._pipeline(text=messages)
        except Exception as exc:  # pragma: no cover - runtime failure
            logger.warning("Qwen OCR inference failed for %s: %s", path, exc)
            return ""
        text = self._extract_generated_text(result)
        return text.strip() if isinstance(text, str) else ""

    def _load_image(self, path: Path) -> Optional[Image.Image]:
        try:
            image = Image.open(path).convert("RGB")
            logger.debug("Loaded image %s (%s, %s)", path, *image.size)
            return image
        except Exception as exc:  # pragma: no cover - IO failure
            logger.warning("Failed to load image %s: %s", path, exc)
            return None

    def _extract_generated_text(self, payload) -> str:
        if payload is None:
            return ""
        if isinstance(payload, list):
            if not payload:
                return ""
            # hf pipeline returns [{"generated_text": [...]}] in multimodal mode
            return self._extract_generated_text(payload[0])
        if isinstance(payload, dict):
            generated = payload.get("generated_text") or payload.get("text")
            if isinstance(generated, list):
                return "\n".join(str(item) for item in generated if item)
            if generated:
                return str(generated)
            # huggingface pipeline sometimes returns {"answer": "..."}
            for key in ("answer", "value"):
                if key in payload and payload[key]:
                    return str(payload[key])
            return ""
        return str(payload)
