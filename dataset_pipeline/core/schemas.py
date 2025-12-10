from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator


Role = Literal["user", "assistant", "system"]


class ParsedMessage(BaseModel):
    """Raw message produced by a parser before role assignment."""

    role: Optional[Role] = None
    content: str = Field(..., min_length=1)
    sender: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("content")
    def strip_content(cls, value: str) -> str:
        return value.strip()


class ParsedDocument(BaseModel):
    """Unified payload emitted by parsers."""

    source: str
    doc_type: Literal["dialogue", "knowledge"]
    parser_type: str
    format: str
    messages: List[ParsedMessage] = Field(default_factory=list)
    knowledge: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageRecord(BaseModel):
    """Single utterance with rich metadata."""

    role: Role
    content: str = Field(..., min_length=1)
    source: str
    sender: Optional[str] = None
    timestamp: Optional[datetime] = None
    emotion: Optional[str] = None
    tone: Optional[str] = None
    topic: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("content")
    def strip_content(cls, value: str) -> str:
        return value.strip()


class DialogueSample(BaseModel):
    """Prompt/response pair ready for supervised fine-tuning."""

    prompt: str = Field(..., min_length=1)
    completion: str = Field(..., min_length=1)
    source: str
    messages: List[MessageRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    """Chunk of factual knowledge extracted from supporting documents."""

    chunk_id: str
    content: str = Field(..., min_length=1)
    source: str
    chunk_index: int
    total_chunks: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Manifest(BaseModel):
    """Summary of pipeline run."""

    persona: str
    created_at: datetime
    config: Dict[str, Any]
    stats: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
