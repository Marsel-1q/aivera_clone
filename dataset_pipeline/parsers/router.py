from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from dataset_pipeline.core.schemas import ParsedDocument

from .hybrid_parser import HybridParser
from .rule_based import RuleBasedParser
from .vlm_parser import VLMParser

logger = logging.getLogger(__name__)


CHAT_KEYWORDS = {"chat", "dialog", "message", "kwork", "whatsapp", "telegram", "dm", "messenger"}
KNOWLEDGE_KEYWORDS = {"resume", "cv", "brief", "spec", "tz", "notes", "profile", "тз", "описание"}


class ParserRouter:
    """Selects the optimal parser for every file."""

    CHAT_EXTENSIONS = {".txt", ".log", ".html", ".htm", ".json", ".jsonl", ".csv"}
    KNOWLEDGE_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown"}

    def __init__(
        self,
        enable_vlm: bool = True,
        prefer_vlm: bool = False,
        vlm_model_id: str = "prithivMLmods/Qwen2-VL-OCR-2B-Instruct",
    ) -> None:
        self.rule_parser = RuleBasedParser()
        self.vlm_parser = VLMParser(model_id=vlm_model_id, enable=enable_vlm, rule_parser=self.rule_parser)
        if not enable_vlm:
            self.vlm_parser = None
        self.hybrid_parser = HybridParser(rule_parser=self.rule_parser, vlm_parser=self.vlm_parser)
        self.prefer_vlm = prefer_vlm

    def parse(self, path: Path) -> Optional[ParsedDocument]:
        parser = self._select_parser(path)
        if parser is None:
            logger.debug("No parser configured for %s", path)
            return None

        doc_type = self._infer_doc_type(path)
        document: Optional[ParsedDocument] = None
        if isinstance(parser, RuleBasedParser):
            document = parser.parse(path)
        elif isinstance(parser, VLMParser):
            document = parser.parse(path, doc_type=doc_type)
        elif isinstance(parser, HybridParser):
            document = parser.parse(path, doc_type=doc_type)

        if document is None and doc_type == "dialogue":
            logger.debug("Falling back to rule-based parser for %s", path)
            document = self.rule_parser.parse(path)
        return document

    def _infer_doc_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        stem = path.stem.lower()
        if any(keyword in stem for keyword in CHAT_KEYWORDS):
            return "dialogue"
        if any(keyword in stem for keyword in KNOWLEDGE_KEYWORDS):
            return "knowledge"
        if suffix in self.KNOWLEDGE_EXTENSIONS:
            return "knowledge"
        if suffix in VLMParser.IMAGE_EXTENSIONS:
            return "dialogue"
        return "dialogue"

    def _select_parser(self, path: Path):
        suffix = path.suffix.lower()
        if self.prefer_vlm and self.vlm_parser and suffix in self.CHAT_EXTENSIONS:
            return self.vlm_parser
        if suffix in self.CHAT_EXTENSIONS:
            return self.rule_parser
        if suffix in VLMParser.IMAGE_EXTENSIONS:
            return self.vlm_parser
        if suffix in self.KNOWLEDGE_EXTENSIONS:
            return self.hybrid_parser
        return None
