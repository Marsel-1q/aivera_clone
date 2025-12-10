#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from .retriever import KnowledgeRetriever, RetrievalResult

logger = logging.getLogger(__name__)


def load_model(
    model_id: str,
    adapter_path: Path | None,
    load_in_4bit: bool = True,
    trust_remote_code: bool = True,
) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    quant_config = None
    if load_in_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    logger.info("Loading base model %s", model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        quantization_config=quant_config,
        trust_remote_code=trust_remote_code,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=trust_remote_code)

    if adapter_path:
        logger.info("Merging LoRA adapter from %s", adapter_path)
        model = PeftModel.from_pretrained(model, adapter_path)
        tokenizer = AutoTokenizer.from_pretrained(adapter_path, trust_remote_code=trust_remote_code)

    model = model.eval()
    if hasattr(model.config, "use_cache"):
        model.config.use_cache = True
    return model, tokenizer


def format_context_snippets(snippets: List[RetrievalResult]) -> str:
    if not snippets:
        return "Контекст отсутствует."
    lines = []
    for item in snippets:
        suffix = f" (источник: {item.source})" if item.source else ""
        lines.append(f"- {item.content}{suffix}")
    return "Контекст:\n" + "\n".join(lines)


def build_messages(
    system_prompt: str,
    user_question: str,
    snippets: List[RetrievalResult],
) -> List[dict]:
    # Убираем блок "Контекст:" и инструкцию "Используй приведённый контекст"
    # Вместо этого делаем контекст частью system prompt
    
    if snippets:
        context_info = "\n".join([f"- {item.content}" for item in snippets])
        enhanced_system = f"{system_prompt}\n\nДоступная информация о товарах:\n{context_info}"
    else:
        enhanced_system = system_prompt
    
    # User prompt — только чистый вопрос, без инструкций
    return [
        {"role": "system", "content": enhanced_system},
        {"role": "user", "content": user_question},
    ]


def generate_answer(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    messages: List[dict],
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 40,
    do_sample: bool = True,
) -> str:
    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature if do_sample else None,
            top_p=top_p if do_sample else None,
            top_k=top_k if do_sample else None,
        )
    generated = output[0][inputs["input_ids"].shape[-1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Answer questions with retrieval-augmented generation.")
    parser.add_argument("question", nargs="?", help="Вопрос пользователя. Если не указан, будет интерактивный режим.")
    parser.add_argument(
        "--system-prompt",
        default="Ты — цифровой клон Марселя. Отвечай уверенно, с лёгким юмором, но по делу.",
        help="Системный промт для модели.",
    )
    parser.add_argument(
        "--model-id",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Базовая модель для инференса.",
    )
    parser.add_argument(
        "--adapter-path",
        type=Path,
        default=Path("outputs/lora_adapter"),
        help="Каталог с обученным LoRA адаптером. Можно опустить для чистой модели.",
    )
    parser.add_argument(
        "--load-in-4bit",
        action="store_true",
        help="Загрузить базовую модель в 4-битном режиме (рекомендуется при ограниченной памяти GPU).",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("data/rag_index"),
        help="Каталог с RAG-индексом (embeddings.npy + records.jsonl).",
    )
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Модель для позиционирования запросов в векторном пространстве.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=4,
        help="Сколько фрагментов знаний добавлять в prompt.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=256,
        help="Максимум новых токенов в ответе.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature для сэмплирования (используется, если не указан --greedy).",
    )
    parser.add_argument(
        "--sample-top-p",
        dest="sample_top_p",
        type=float,
        default=0.9,
        help="Nucleus sampling порог (используется, если не указан --greedy).",
    )
    parser.add_argument(
        "--sample-top-k",
        dest="sample_top_k",
        type=int,
        default=40,
        help="Ограничение top-k при сэмплировании (используется, если не указан --greedy).",
    )
    parser.add_argument(
        "--greedy",
        action="store_true",
        help="Отключить сэмплирование и генерировать детерминированно.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def interactive_loop(
    retriever: KnowledgeRetriever,
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    system_prompt: str,
    top_k: int,
    max_new_tokens: int,
    temperature: float,
    sample_top_p: float,
    sample_top_k: int,
    greedy: bool,
) -> None:
    print("RAG чат. Введите вопрос (или пустую строку для выхода).")
    while True:
        try:
            question = input(">>> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            return
        if not question:
            print("Выход.")
            return
        snippets = retriever.search(question, k=top_k)
        messages = build_messages(system_prompt, question, snippets)
        answer = generate_answer(
            model,
            tokenizer,
            messages,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=sample_top_p,
            top_k=sample_top_k,
            do_sample=not greedy,
        )
        print(answer)
        if snippets:
            print("---")
            for item in snippets:
                meta = f" | источник: {item.source}" if item.source else ""
                print(f"score={item.score:.3f}{meta}\n{item.content}\n")


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    retriever = KnowledgeRetriever(
        index_dir=args.index_dir,
        embedding_model=args.embedding_model,
    )
    adapter_path = args.adapter_path if args.adapter_path.exists() else None
    model, tokenizer = load_model(
        model_id=args.model_id,
        adapter_path=adapter_path,
        load_in_4bit=args.load_in_4bit,
    )
    if args.question:
        snippets = retriever.search(args.question, k=args.top_k)
        messages = build_messages(args.system_prompt, args.question, snippets)
        answer = generate_answer(
            model,
            tokenizer,
            messages,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_p=args.sample_top_p,
            top_k=args.sample_top_k,
            do_sample=not args.greedy,
        )
        print(answer)
        if snippets:
            print("\n--- Контекст ---")
            for item in snippets:
                suffix = f" (источник: {item.source})" if item.source else ""
                print(f"[score={item.score:.3f}]{suffix}\n{item.content}\n")
    else:
        interactive_loop(
            retriever=retriever,
            model=model,
            tokenizer=tokenizer,
            system_prompt=args.system_prompt,
            top_k=args.top_k,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            sample_top_p=args.sample_top_p,
            sample_top_k=args.sample_top_k,
            greedy=args.greedy,
        )


if __name__ == "__main__":
    main()
