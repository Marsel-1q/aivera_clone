#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
    AutoTokenizer,
    Qwen2_5_VLForConditionalGeneration,
)
from rag.retriever import KnowledgeRetriever, RetrievalResult


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chat with base model + LoRA adapter.")
    parser.add_argument("--model-id", required=True, help="Base model ID or path.")
    parser.add_argument("--adapter-dir", required=True, help="Path to LoRA adapter dir.")
    parser.add_argument("--message", required=True, help="User message.")
    parser.add_argument("--system-prompt", default="", help="Optional system prompt.")
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--rag-index-dir", type=Path, help="Path to RAG index (embeddings.npy + records.jsonl).")
    parser.add_argument("--embedding-model", default="sentence-transformers/all-MiniLM-L6-v2", help="Embedding model id.")
    parser.add_argument("--top-k", type=int, default=4, help="How many knowledge snippets to include.")
    return parser.parse_args()


def maybe_retrieve(args: argparse.Namespace) -> tuple[list[RetrievalResult], str]:
    """Fetch relevant snippets and return enhanced system prompt."""
    base_system = args.system_prompt or "You are a helpful assistant."
    if not args.rag_index_dir:
        return [], base_system

    try:
        retriever = KnowledgeRetriever(index_dir=Path(args.rag_index_dir), embedding_model=args.embedding_model)
        snippets = retriever.search(args.message, k=max(1, args.top_k))
        if not snippets:
            return [], base_system
        context = "\n".join([f"- {item.content}" for item in snippets])
        enhanced = f"{base_system}\n\nContext:\n{context}"
        return snippets, enhanced
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] RAG disabled: {exc}", file=sys.stderr)
        return [], base_system


def main() -> None:
    args = parse_args()

    if not Path(args.adapter_dir).exists():
        print(f"Adapter dir not found: {args.adapter_dir}", file=sys.stderr)
        sys.exit(1)

    snippets, system_prompt = maybe_retrieve(args)
    model_id_lower = args.model_id.lower()
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    # Qwen2.5-VL (and другие VL) требуют специфический класс, AutoModelForCausalLM не подходит.
    if "qwen" in model_id_lower and "vl" in model_id_lower:
        processor = AutoProcessor.from_pretrained(args.model_id, trust_remote_code=True)
        base_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            args.model_id,
            trust_remote_code=True,
            device_map="auto",
            dtype=dtype,
        )
        model = PeftModel.from_pretrained(base_model, args.adapter_dir)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": args.message},
        ]

        chat_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[chat_text], return_tensors="pt").to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=True)
        # срезаем входные токены, чтобы получить только ответ
        gen_ids = outputs[0][inputs["input_ids"].shape[-1] :]
        text = processor.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
        print(text)
        return

    # Текстовые модели (fallback)
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        trust_remote_code=True,
        device_map="auto",
        dtype=dtype,
    )
    model = PeftModel.from_pretrained(base_model, args.adapter_dir)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": args.message},
    ]

    if hasattr(tokenizer, "apply_chat_template"):
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages]) + "\nassistant:"

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=True)
    gen = output[0][inputs["input_ids"].shape[-1]:]
    text = tokenizer.decode(gen, skip_special_tokens=True).strip()
    print(text)


if __name__ == "__main__":
    main()
