from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from dataset_pipeline.core import (
    KnowledgeChunk,
    Manifest,
    chunk_text,
    ensure_directory,
    iter_source_files,
    merge_metadata,
    text_digest,
    validate_dialogue_samples,
    validate_knowledge_chunks,
)
from dataset_pipeline.parsers import ParserRouter
from dataset_pipeline.processing import build_multi_turn_pairs, format_samples, prepare_message_records, split_dialogues

logger = logging.getLogger("dataset_pipeline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pure parsing pipeline for persona datasets.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Paths with raw data.")
    parser.add_argument("--output-dir", required=True, help="Directory for processed dataset.")
    parser.add_argument("--persona", required=True, help="Primary persona identifier.")
    parser.add_argument(
        "--persona-aliases",
        nargs="*",
        default=(),
        help="Additional aliases matching assistant messages.",
    )
    parser.add_argument(
        "--eval-split",
        type=float,
        default=0.1,
        help="Fraction of validation data (default: 0.1).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for shuffling.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=220,
        help="Knowledge chunk size (words).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=30,
        help="Chunk overlap (words).",
    )
    vlm_group = parser.add_mutually_exclusive_group()
    vlm_group.add_argument(
        "--enable-vlm",
        dest="enable_vlm",
        action="store_true",
        help="Enable Qwen2-VL OCR parser for images.",
    )
    vlm_group.add_argument(
        "--disable-vlm",
        dest="enable_vlm",
        action="store_false",
        help="Disable Qwen2-VL OCR parser.",
    )
    parser.set_defaults(enable_vlm=True)
    parser.add_argument(
        "--prefer-vlm",
        action="store_true",
        help="Use VLM even for textual chat formats (slower).",
    )
    parser.add_argument(
        "--vlm-model",
        default="prithivMLmods/Qwen2-VL-OCR-2B-Instruct",
        help="Model identifier for OCR parser.",
    )
    parser.add_argument(
        "--format",
        choices=["huggingface", "sharegpt", "instruct"],
        default="huggingface",
        help="Output format for train/eval JSONL.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def collect_files(input_dirs: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    for root in input_dirs:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            logger.warning("Input path does not exist: %s", root_path)
            continue
        if root_path.is_file():
            files.append(root_path)
        else:
            files.extend(iter_source_files(root_path))
    return files


def write_jsonl(path: Path, records: Iterable[Dict]) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_knowledge_chunks(
    documents: Sequence,
    chunk_size: int,
    overlap: int,
) -> List[KnowledgeChunk]:
    chunks: List[KnowledgeChunk] = []
    for doc in documents:
        if not getattr(doc, "knowledge", None):
            continue
        text = str(doc.knowledge).strip()
        if not text:
            continue
        chunk_words = list(chunk_text(text, chunk_size=chunk_size, overlap=overlap))
        total = len(chunk_words)
        for index, content in chunk_words:
            digest = text_digest(f"{doc.source}:{index}:{content[:50]}")
            metadata = merge_metadata(doc.metadata or {}, {"parser_type": doc.parser_type})
            chunks.append(
                KnowledgeChunk(
                    chunk_id=digest,
                    content=content,
                    source=doc.source,
                    chunk_index=index,
                    total_chunks=total,
                    metadata=metadata,
                )
            )
    return chunks


def build_other_records(documents: Sequence) -> List[Dict]:
    other_records: List[Dict] = []
    for doc in documents:
        raw_text = None
        if isinstance(doc.metadata, dict):
            raw_text = doc.metadata.get("raw_text")
        if not raw_text and doc.doc_type == "knowledge":
            raw_text = getattr(doc, "knowledge", None)
        if not raw_text:
            continue
        other_records.append(
            {
                "source": doc.source,
                "parser_type": doc.parser_type,
                "content": raw_text,
                "metadata": doc.metadata,
            }
        )
    return other_records


def build_manifest(
    persona: str,
    args: argparse.Namespace,
    stats: Dict[str, int],
) -> Manifest:
    return Manifest(
        persona=persona,
        created_at=datetime.now(timezone.utc),
        config={
            "eval_split": args.eval_split,
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "inputs": [str(Path(p).resolve()) for p in args.inputs],
            "format": args.format,
            "enable_vlm": args.enable_vlm,
            "prefer_vlm": args.prefer_vlm,
        },
        stats=stats,
    )


def run_pipeline(args: argparse.Namespace) -> None:
    setup_logging(args.log_level)
    logger.info("Starting dataset pipeline.")

    if not 0 < args.eval_split < 1:
        raise ValueError("--eval-split must be between 0 and 1.")

    files = collect_files(args.inputs)
    logger.info("Discovered %d source files.", len(files))

    router = ParserRouter(enable_vlm=args.enable_vlm, prefer_vlm=args.prefer_vlm, vlm_model_id=args.vlm_model)

    parsed_documents = []
    for path in files:
        document = router.parse(path)
        if document:
            parsed_documents.append(document)
        else:
            logger.warning("No parser output for %s", path)

    dialogue_docs = [doc for doc in parsed_documents if doc.doc_type == "dialogue"]
    knowledge_docs = [doc for doc in parsed_documents if doc.doc_type == "knowledge"]

    persona_aliases = [args.persona] + list(args.persona_aliases or [])
    message_records = prepare_message_records(dialogue_docs, persona_aliases=persona_aliases)
    dialogue_samples = validate_dialogue_samples(build_multi_turn_pairs(message_records))
    train_split, eval_split = split_dialogues(dialogue_samples, args.eval_split, args.seed)

    knowledge_chunks = validate_knowledge_chunks(
        build_knowledge_chunks(knowledge_docs, chunk_size=args.chunk_size, overlap=args.chunk_overlap)
    )
    other_records = build_other_records(parsed_documents)

    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "train.jsonl", format_samples(train_split, args.format))
    write_jsonl(output_dir / "eval.jsonl", format_samples(eval_split, args.format))
    write_jsonl(
        output_dir / "knowledge.jsonl",
        (chunk.model_dump() for chunk in knowledge_chunks),
    )
    if other_records:
        write_jsonl(output_dir / "other.jsonl", other_records)

    manifest = build_manifest(
        persona=args.persona,
        args=args,
        stats={
            "parsed_documents": len(parsed_documents),
            "dialogue_documents": len(dialogue_docs),
            "knowledge_documents": len(knowledge_docs),
            "dialogue_samples": len(dialogue_samples),
            "train_samples": len(train_split),
            "eval_samples": len(eval_split),
            "knowledge_chunks": len(knowledge_chunks),
            "other_records": len(other_records),
        },
    )
    manifest_path = output_dir / "manifest.json"
    ensure_directory(manifest_path.parent)
    manifest_payload = manifest.model_dump()
    manifest_payload["created_at"] = manifest.created_at.isoformat()
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Pipeline complete. Output saved to %s", output_dir)


def main() -> None:  # pragma: no cover
    args = parse_args()
    run_pipeline(args)


if __name__ == "__main__":  # pragma: no cover
    main()
