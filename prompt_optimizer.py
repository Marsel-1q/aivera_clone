#!/usr/bin/env python3
"""Autonomous prompt optimisation loop for the persona clone."""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
from openai import OpenAI
from peft import PeftModel
from PIL import Image
from transformers import AutoProcessor, BitsAndBytesConfig, Glm4vForConditionalGeneration, Qwen2_5_VLForConditionalGeneration

from qwen_vl_utils import process_vision_info

from train_qlora import TrainingRunResult, parse_args as parse_train_args, run_training
from rag.retriever import KnowledgeRetriever, RetrievalResult

try:  # pragma: no cover - optional dependency provided by transformers
    from jinja2.exceptions import TemplateError  # type: ignore
except ImportError:  # pragma: no cover
    TemplateError = RuntimeError  # fallback type


JUDGE_DIALOG_SYSTEM_PROMPT = (
    """Ты — требовательный, но реальный клиент, который переписывается с цифровым клоном эксперта. 
    Всегда начинай диалог с живой фразы, а не формальной формулы. 
    Веди себя как живой человек: задавай уточняющие вопросы, проси примеры и подробности, сомневайся, корректно спорь по существу, 
    если чувствуешь фальшь. Проверяй работу с витриной: регулярно спрашивай цены, состав, порции, наличие размеров, проси ссылки/фото, 
    сравнивай ответы с фактическим контекстом. Следи за естественностью: замечай любые странные или нехарактерные фразы 
    (особенно религиозные обороты — если в речи такие не встречались ранее, считай их странными), повторные приветствия, неестественные повторы. 
    Реагируй на неестественность с удивлением или лёгкой иронией. Говори только по-русски. Каждый раз возвращай лишь новую живую фразу клиента, 
    без инструкций и форматирования.
"""
)

JUDGE_EVALUATION_SYSTEM_PROMPT = (
    """Ты — строгий, но объективный судья диалогов между цифровым клоном и клиентом. Твоя задача — проанализировать последнюю (или выделенную) реплику клона и быстро оценить:
1. Насколько хорошо она соответствует индивидуальному стилю, специфике и нормам оригинального человека (профессионализм, простота, эмпатия, характерные выражения, уместные шутки, вежливая речь, особенности культуры, религии и т.п.).
2. Насколько грамотно и честно клоном используются актуальные факты: только реальные данные (цены, наличие, характеристики, конкретные услуги или товары, специфика ограничений, честные признания о незнании, прозрачные ответы на недочёты).

**Особое внимание:**
- Уважай культурные, религиозные, профессиональные и личные особенности оригинала.
- Считай нарушением любые шаблонные, повторяющиеся или фальшивые фразы, неестественные обороты, неуместные приветствия, чрезмерную формальность или навязчивую стилизацию — если это не свойственно оригиналу или противоречит реакции клиента.
- Если клиент явно или косвенно просит сменить стиль, уменьшить формализм, не использовать специфические фразы (религиозные, профессиональные, сленг, и т.п.), клон должен адаптироваться — оценка снижается, если этого не произошло.

**Шкала оценки:**
- 90-100: стиль, интонация, факты и адаптивность — идеально, полностью аутентично.
- 80-89: небольшие огрехи, но оригинальность и индивидуальность сохранены.
- 70-79: заметные минусы, недоработки, единичные неестественные элементы.
- 60-69: роботизированный или скучный тон, мало фактов, плохо узнаваем стиль.
- 50-59: ярко выраженные ошибки — шаблоны, повторы, игнорирование явных пожеланий клиента, выдумки.
- <50: критический провал (много фальши, сильный разрыв с личностью оригинала или его нормами).

**Всегда принимай во внимание:**
- Не суди за использование специфических выражений, если они реально отражают стиль человека или обоснованы ситуацией и реакцией клиента.
- Если реакция клиента явно требует сменить стиль или речь, клон обязан адаптироваться — за неадаптивность автоматически снижай баллы.

Ответ только чистый JSON:
{"score": <0-100>, "feedback": "..."}
"""
)

PROMPT_COACH_SYSTEM_PROMPT = (
    """Ты — эксперт по prompt engineering. Твоя задача: анализировать системный промт диалогового клона и обновлять его так, чтобы стиль общения максимально совпадал с индивидуальностью оригинала (его речью, культурой, привычками, реакцией на просьбы клиента). 

Что обязательно нужно учесть:
- Если ассистент отвечает шаблонно, роботизировано, повторяет инструкции или использует неестественные для оригинала выражения, обязательно исправляй промт.
- Системный промт должен быть адаптивным: явно указывать, что просьбы клиента (например, сменить стиль, не использовать профессиональный или религиозный сленг, уменьшить формализм, говорить проще, неуместное добавление фраз, повторение фраз ) имеют приоритет над общими установками — ассистент обязан подстраиваться на ходу. Если клон повторяет слова, то скорее всего не понимает когда эти фразы использовать, подправляй промпт так с четкими указаниями когда нужно использовать эти фразы
- Для любых культурных, профессиональных или личностных особенностей (специфичные фразы, приветствия, этикет, юмор) опиши чёткие правила, когда и как их уместно использовать, а когда — нет (например, лимит «1 раз за диалог» или только «по конкретному поводу»).
- Удали из промта все фразы, которые могут отзеркаливаться в ответах либо провоцируют шаблонное поведение, роботизированный стиль или повтор инструкций.
- Приведи пример хорошего адаптивного ответа в стиле оригинала, а также пример корректной реакции на просьбу клиента изменить стиль.

Ответ всегда только JSON:
{
  "system_prompt": "<адаптированный промт для конкретного клона>",
  "reasoning": "<пояснение, какие ошибки исправлены и почему>"
}
"""
)

JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(slots=True)
class TurnLog:
    turn_index: int
    judge_question: str
    clone_answer: str
    score: float
    feedback: str
    raw_evaluation: str


@dataclass(slots=True)
class IterationResult:
    iteration: int
    system_prompt: str
    scenarios: List["ScenarioResult"]
    average_score: float
    adapter_dir: Path
    output_dir: Path
    train_metrics: Dict[str, Any]
    improvement_reason: Optional[str] = None
    improved_prompt: Optional[str] = None


@dataclass(slots=True)
class ScenarioResult:
    scenario_index: int
    turns: List[TurnLog]
    average_score: float


@dataclass(slots=True)
class PromptOptimizationSummary:
    success: bool
    target_score: float
    best_iteration: int
    best_score: float
    best_prompt: str
    iterations: List[IterationResult]


def load_train_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Train config not found: {config_path}")
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - runtime validation
        raise ValueError(f"Failed to parse JSON config {config_path}: {exc}") from exc


def resolve_text_arg(direct: Optional[str], file_path: Optional[Path]) -> Optional[str]:
    if file_path is not None:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return file_path.read_text(encoding="utf-8").strip()
    if direct is not None:
        return direct.strip()
    return None


def ensure_prompt(initial: Optional[str], fallback: Optional[str], label: str) -> str:
    value = initial or fallback
    if not value:
        raise ValueError(f"{label} не указан: добавьте через аргументы CLI или в конфиге train_qlora")
    return value.strip()


def extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        if content.get("type") == "text":
            text = content.get("text")
            if isinstance(text, str):
                return text.strip()
        if "content" in content:
            return extract_text_from_content(content["content"])
        if "text" in content and isinstance(content["text"], str):
            return content["text"].strip()
        if "value" in content and isinstance(content["value"], str):
            return content["value"].strip()
        return ""
    if isinstance(content, (list, tuple)):
        fragments: List[str] = []
        for item in content:
            text = extract_text_from_content(item)
            if text:
                fragments.append(text)
        return " ".join(fragments).strip()
    if content is None:
        return ""
    return str(content).strip()


def last_user_message(history: Sequence[Dict[str, Any]]) -> Optional[str]:
    for message in reversed(history):
        if message.get("role") == "user":
            content = extract_text_from_content(message.get("content"))
            if content:
                return content
    return None


def last_assistant_message(history: Sequence[Dict[str, Any]]) -> Optional[str]:
    for message in reversed(history):
        if message.get("role") == "assistant":
            content = extract_text_from_content(message.get("content"))
            if content:
                return content
    return None


def format_retrieval_snippets(snippets: Sequence[RetrievalResult]) -> str:
    lines: List[str] = []
    for snippet in snippets:
        content = (snippet.content or "").strip()
        if not content:
            continue
        suffix = f" (источник: {snippet.source})" if snippet.source else ""
        lines.append(f"- {content}{suffix}")
    return "\n".join(lines)


def config_to_cli_args(config: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for key, value in config.items():
        if value is None:
            continue
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                args.append(flag)
            continue
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            args.append(flag)
            args.extend(str(item) for item in value)
            continue
        if isinstance(value, dict):
            raise ValueError(f"Nested config is not supported for key '{key}'")
        args.extend([flag, str(value)])
    return args


def infer_backend_from_model_id(model_id: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    lowered = (model_id or "").lower()
    if "qwen" in lowered and "vl" in lowered:
        return "qwen2_vl"
    if "glm" in lowered:
        return "glm4v"
    raise ValueError("Не удалось определить VL-бэкенд: задайте vl_backend в конфиге train_qlora.")


def extract_image_refs_from_message(message: Dict[str, Any]) -> List[str]:
    refs: List[str] = []

    def _extend(value: Any) -> None:
        if isinstance(value, str) and value:
            refs.append(value)
            return
        if isinstance(value, dict):
            candidate = value.get("image") or value.get("url") or value.get("path")
            if isinstance(candidate, str) and candidate:
                refs.append(candidate)
            for key in ("images", "media", "attachments", "value"):
                if key in value:
                    _extend(value[key])
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                _extend(item)

    for key in ("images", "image", "image_path", "image_paths", "media", "attachments"):
        if key in message:
            _extend(message[key])

    metadata = message.get("metadata")
    if isinstance(metadata, dict):
        for key in ("images", "image", "attachments", "media"):
            if key in metadata:
                _extend(metadata[key])

    seen: set[str] = set()
    result: List[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return result


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
        logging.warning("Изображение %s не найдено.", ref)
        return None
    try:
        with Image.open(path) as img:
            return img.convert("RGB")
    except Exception as exc:
        logging.warning("Не удалось загрузить изображение %s: %s", ref, exc)
        return None


def to_multimodal_blocks(content: Any) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []

    def _append(block: Dict[str, Any]) -> None:
        if not block:
            return
        block_type = block.get("type")
        if block_type == "image":
            image_ref = block.get("image") or block.get("url") or block.get("path")
            if isinstance(image_ref, str) and image_ref:
                blocks.append({"type": "image", "image": image_ref})
            return
        if block_type == "text":
            text = extract_text_from_content(block.get("text"))
            if text:
                blocks.append({"type": "text", "text": text})
            return
        if block_type:
            blocks.append(block)
            return
        text = extract_text_from_content(block)
        if text:
            blocks.append({"type": "text", "text": text})

    def _collect(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, dict):
            block_type = item.get("type")
            if block_type:
                _append(item)
                return
            if "content" in item:
                _collect(item["content"])
            if "text" in item:
                text_block = {"type": "text", "text": item.get("text")}
                _append(text_block)
            for key in ("image", "url", "path"):
                ref = item.get(key)
                if isinstance(ref, str) and ref:
                    _append({"type": "image", "image": ref})
            for key in ("images", "media", "attachments", "values"):
                if key in item:
                    _collect(item[key])
            return
        if isinstance(item, (list, tuple, set)):
            for sub in item:
                _collect(sub)
            return
        if isinstance(item, str):
            text = item.strip()
            if text:
                blocks.append({"type": "text", "text": text})
            return
        text = str(item).strip()
        if text:
            blocks.append({"type": "text", "text": text})

    _collect(content)
    return blocks


def convert_message_for_vl(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    role = str(message.get("role") or "user")
    blocks = to_multimodal_blocks(message.get("content"))
    existing_images = {
        block.get("image")
        for block in blocks
        if block.get("type") == "image" and block.get("image")
    }
    for ref in extract_image_refs_from_message(message):
        if ref not in existing_images:
            blocks.append({"type": "image", "image": ref})
            existing_images.add(ref)
    if not blocks:
        text = extract_text_from_content(message.get("content"))
        if not text:
            return None
        blocks.append({"type": "text", "text": text})
    return {"role": role, "content": blocks}


def prepare_glm_messages(messages: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Image.Image]]:
    converted: List[Dict[str, Any]] = []
    images: List[Image.Image] = []
    for message in messages:
        role = message.get("role") or "user"
        content = message.get("content") or []
        if isinstance(content, dict):
            content = [content]
        if not isinstance(content, list):
            content = [{"type": "text", "text": str(content)}]

        new_blocks: List[Dict[str, Any]] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "image":
                ref = block.get("image") or block.get("url") or block.get("path")
                img = load_image_from_ref(ref)
                if img is not None:
                    new_blocks.append({"type": "image", "image": img})
                    images.append(img)
                continue
            text = extract_text_from_content(block if isinstance(block, dict) else block)
            if text:
                new_blocks.append({"type": "text", "text": text})
        if not new_blocks:
            new_blocks.append({"type": "text", "text": ""})
        converted.append({"role": role, "content": new_blocks})
    return converted, images


def format_history(messages: Sequence[Dict[str, Any]]) -> str:
    if not messages:
        return "История диалога пуста. Начинай беседу."
    lines: List[str] = []
    for idx, message in enumerate(messages, start=1):
        role = message.get("role", "")
        content = extract_text_from_content(message.get("content"))
        speaker = "Клиент" if role == "user" else "Клон"
        lines.append(f"{idx:02d}. {speaker}: {content}")
    return "\n".join(lines)


def extract_json_object(payload: str) -> Dict[str, Any]:
    payload = payload.strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = JSON_PATTERN.search(payload)
        if not match:
            raise ValueError(f"Не удалось распарсить JSON из ответа судьи: {payload}")
        return json.loads(match.group(0))


def empty_cuda_cache() -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class JudgeClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "not-needed",
        temperature: float = 0.75,
        retriever: Optional[KnowledgeRetriever] = None,
        rag_top_k: int = 4,
    ) -> None:
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.retriever = retriever
        self.rag_top_k = rag_top_k

    def _chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
        )
        return (completion.choices[0].message.content or "").strip()

    def ask_question(
        self,
        history: Sequence[Dict[str, Any]],
        expected_style: str,
    ) -> str:
        messages = [
            {"role": "system", "content": JUDGE_DIALOG_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Стиль, который должен проверять эксперт: {expected_style}.\n\n"
                    f"История диалога:\n{format_history(history)}\n\n"
                    "Сформулируй следующую реплику клиента и верни только её."
                ),
            },
        ]
        return self._chat(messages)

    def evaluate_turn(
        self,
        history: Sequence[Dict[str, Any]],
        expected_style: str,
    ) -> Dict[str, Any]:
        knowledge_section = "Контекст знаний для проверки: данных нет. Если факт отсутствует, честно укажи, что данных нет, и не выдумывай." 
        if self.retriever is not None:
            queries: List[str] = []
            question_text = last_user_message(history)
            answer_text = last_assistant_message(history)
            if question_text:
                queries.append(question_text)
            if answer_text:
                queries.append(answer_text)

            seen: set[str] = set()
            snippets: List[RetrievalResult] = []
            for query in queries:
                if not query:
                    continue
                for snippet in self.retriever.search(query, k=self.rag_top_k):
                    key = (snippet.content or "").strip()
                    if not key or key in seen:
                        continue
                    snippets.append(snippet)
                    seen.add(key)

            formatted = format_retrieval_snippets(snippets)
            if formatted:
                knowledge_section = (
                    "Контекст знаний для проверки (используй только перечисленные факты; если факта нет, признай, что данных нет и не придумывай):\n"
                    f"{formatted}"
                )
        messages = [
            {"role": "system", "content": JUDGE_EVALUATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Эталонный стиль: {expected_style}.\n"
                    "Оцени соответствие последней реплики ассистента ожиданиям.\n"
                    f"{knowledge_section}\n\n"
                    f"Диалог:\n{format_history(history)}"
                ),
            },
        ]
        logging.debug("Judge evaluation контекст:\n%s", knowledge_section)
        response = self._chat(messages, temperature=0.0)
        return extract_json_object(response)

    def improve_prompt(
        self,
        current_prompt: str,
        expected_style: str,
        feedback_summary: str,
        average_score: float,
    ) -> Dict[str, str]:
        messages = [
            {"role": "system", "content": PROMPT_COACH_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Текущий системный промт:\n{current_prompt}\n\n"
                    f"Ожидаемый стиль: {expected_style}\n"
                    f"Средний балл: {average_score:.2f}\n"
                    f"Основные проблемы:\n{feedback_summary.strip() or 'нет данных'}\n\n"
                    "Улучши промт, чтобы повысить схожесть."
                ),
            },
        ]
        response = self._chat(messages, temperature=0.2)
        return extract_json_object(response)


class CloneResponder:
    def __init__(
        self,
        model_id: str,
        adapter_dir: Path,
        precision: str = "4bit",
        trust_remote_code: bool = True,
        retriever: Optional[KnowledgeRetriever] = None,
        rag_top_k: int = 4,
        vl_backend: Optional[str] = None,
    ) -> None:
        self.precision = precision
        self.retriever = retriever
        self.rag_top_k = rag_top_k
        self.backend = infer_backend_from_model_id(model_id, vl_backend)
        self.supports_videos = self.backend == "qwen2_vl"
        quant_config = None
        load_kwargs: Dict[str, Any] = {
            "device_map": "auto",
            "trust_remote_code": trust_remote_code,
        }

        if precision == "4bit":
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            load_kwargs["quantization_config"] = quant_config
        elif precision == "fp16":
            load_kwargs["torch_dtype"] = torch.float16
        elif precision == "fp32":
            load_kwargs["torch_dtype"] = torch.float32
        else:
            raise ValueError(f"Неизвестная точность загрузки модели: {precision}")

        processor_loaded = False
        processor_candidates = [adapter_dir, model_id]
        self.processor: AutoProcessor
        for source in processor_candidates:
            try:
                self.processor = AutoProcessor.from_pretrained(source, trust_remote_code=trust_remote_code)
                processor_loaded = True
                break
            except Exception:
                continue
        if not processor_loaded:
            raise RuntimeError(f"Не удалось загрузить процессор для модели {model_id}")
        if hasattr(self.processor, "tokenizer") and self.processor.tokenizer is not None:
            tokenizer = self.processor.tokenizer
            if getattr(tokenizer, "pad_token_id", None) is None and getattr(tokenizer, "eos_token_id", None) is not None:
                tokenizer.pad_token_id = tokenizer.eos_token_id
            tokenizer.padding_side = "right"

        if self.backend == "qwen2_vl":
            self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(model_id, **load_kwargs)
        else:
            self.model = Glm4vForConditionalGeneration.from_pretrained(model_id, **load_kwargs)
        if not adapter_dir.exists():
            raise FileNotFoundError(f"LoRA adapter not found: {adapter_dir}")

        self.model = PeftModel.from_pretrained(self.model, adapter_dir)
        self.model = self.model.eval()
        if hasattr(self.model.config, "use_cache"):
            self.model.config.use_cache = True
        try:
            self.device = next(self.model.parameters()).device
        except StopIteration:  # pragma: no cover - defensive for empty parameters
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def generate(
        self,
        system_prompt: str,
        history: Sequence[Dict[str, Any]],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        do_sample: bool,
    ) -> str:
        if self.backend == "qwen2_vl":
            return self._generate_qwen(
                system_prompt,
                history,
                max_new_tokens,
                temperature,
                top_p,
                top_k,
                do_sample,
            )
        return self._generate_glm(
            system_prompt,
            history,
            max_new_tokens,
            temperature,
            top_p,
            top_k,
            do_sample,
        )

    def _generate_qwen(
        self,
        system_prompt: str,
        history: Sequence[Dict[str, Any]],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        do_sample: bool,
    ) -> str:
        system_content = system_prompt
        context_snippets: List[RetrievalResult] = []
        if self.retriever is not None:
            query = last_user_message(history)
            if query:
                context_snippets = self.retriever.search(query, k=self.rag_top_k)
        if context_snippets:
            formatted = format_retrieval_snippets(context_snippets)
            if formatted:
                system_content = (
                    f"{system_prompt}\n\n"
                    "Используй факты ниже строго по делу. Не выдумывай лишних брендов или цен, не цитируй дословно с кавычками."
                    " Пересказывай естественно от первого лица.\n"
                    f"Контекст:\n{formatted}"
                )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": [{"type": "text", "text": system_content}]}
        ]
        for message in history:
            converted = convert_message_for_vl(message)
            if converted:
                messages.append(converted)

        prompt_text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        needs_images = False
        needs_videos = False
        for message in messages:
            content = message.get("content") or []
            if isinstance(content, dict):
                content = [content]
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "image":
                    needs_images = True
                elif block_type == "video":
                    needs_videos = True
            if needs_images and (needs_videos or not self.supports_videos):
                break

        image_inputs = None
        video_inputs = None
        if needs_images or (self.supports_videos and needs_videos):
            image_inputs, video_inputs = process_vision_info(messages)

        processor_kwargs: Dict[str, Any] = {
            "text": [prompt_text],
            "padding": True,
            "return_tensors": "pt",
        }
        if image_inputs is not None:
            processor_kwargs["images"] = image_inputs
        if self.supports_videos and video_inputs is not None:
            processor_kwargs["videos"] = video_inputs

        processor_outputs = self.processor(**processor_kwargs)
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in processor_outputs.items()
        }
        generation_kwargs: Dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
        }
        if do_sample:
            generation_kwargs.update({
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
            })
        with torch.no_grad():
            output = self.model.generate(**inputs, **generation_kwargs)
        input_length = inputs["input_ids"].shape[-1]
        generated = output[:, input_length:]
        texts = self.processor.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        return texts[0].strip() if texts else ""

    def _generate_glm(
        self,
        system_prompt: str,
        history: Sequence[Dict[str, Any]],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        do_sample: bool,
    ) -> str:
        messages_sequence: List[Dict[str, Any]] = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]}
        ]
        for message in history:
            converted = convert_message_for_vl(message)
            if converted:
                messages_sequence.append(converted)

        glm_messages, glm_images = prepare_glm_messages(messages_sequence)

        prompt_text: str
        try:
            prompt_text = self.processor.apply_chat_template(
                glm_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logging.debug("GLM chat template failed, falling back to manual prompt: %s", exc)
            prompt_lines: List[str] = []
            for message in glm_messages:
                role = message.get("role", "user")
                content_blocks = message.get("content") or []
                fragments: List[str] = []
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_value = block.get("text")
                        if isinstance(text_value, str) and text_value.strip():
                            fragments.append(text_value.strip())
                if fragments:
                    prompt_lines.append(f"{role}: {' '.join(fragments)}")
            prompt_text = "\n".join(prompt_lines).strip()
        if not prompt_text:
            prompt_text = " "

        processor_kwargs: Dict[str, Any] = {
            "text": [prompt_text],
            "padding": True,
            "return_tensors": "pt",
        }
        if glm_images:
            processor_kwargs["images"] = [glm_images]

        inputs_raw = self.processor(**processor_kwargs)
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs_raw.items()
        }

        generation_kwargs: Dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
        }
        if do_sample:
            generation_kwargs.update(
                {
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                }
            )

        with torch.no_grad():
            output = self.model.generate(**inputs, **generation_kwargs)
        input_length = inputs["input_ids"].shape[-1]
        generated = output[:, input_length:]
        decoded = self.processor.decode(
            generated[0],
            skip_special_tokens=True,
        )
        return decoded.strip()

    def shutdown(self) -> None:
        del self.model
        if hasattr(self, "processor"):
            del self.processor
        empty_cuda_cache()


class PromptOptimizationRunner:
    def __init__(
        self,
        train_config: Dict[str, Any],
        initial_prompt: str,
        expected_style: str,
        judge_client: JudgeClient,
        experiment_root: Path,
        target_score: float,
        max_iterations: int,
        turns_per_dialog: int,
        scenarios_per_iteration: int,
        clone_settings: Dict[str, Any],
        retriever: Optional[KnowledgeRetriever] = None,
    ) -> None:
        self.train_config = train_config
        self.initial_prompt = initial_prompt
        self.expected_style = expected_style
        self.judge = judge_client
        self.experiment_root = experiment_root
        self.target_score = target_score
        self.max_iterations = max_iterations
        self.turns_per_dialog = turns_per_dialog
        self.scenarios_per_iteration = max(1, scenarios_per_iteration)
        self.clone_settings = clone_settings
        self.retriever = retriever

        self.model_id = str(train_config.get("model_id"))
        if not self.model_id:
            raise ValueError("train_config must include 'model_id'")
        self.vl_backend = infer_backend_from_model_id(
            self.model_id,
            train_config.get("vl_backend"),
        )
        self.trust_remote_code = bool(train_config.get("trust_remote_code", True))

    def run(self) -> PromptOptimizationSummary:
        self.experiment_root.mkdir(parents=True, exist_ok=True)

        iterations: List[IterationResult] = []
        best_result: Optional[IterationResult] = None
        current_prompt = self.initial_prompt

        for iteration in range(1, self.max_iterations + 1):
            logging.info("==== Итерация %d началась ====", iteration)
            iteration_dir = self.experiment_root / f"iteration_{iteration:02d}"
            iteration_dir.mkdir(parents=True, exist_ok=True)

            training_result = self._train_model(iteration, current_prompt, iteration_dir)

            iteration_result = self._evaluate_with_judge(
                system_prompt=current_prompt,
                adapter_dir=training_result.adapter_dir,
                iteration=iteration,
                output_dir=training_result.output_dir,
                train_metrics=training_result.train_metrics,
            )

            scenario_results = iteration_result.scenarios
            average_score = iteration_result.average_score

            self._write_iteration_artifacts(iteration_dir, iteration_result)
            iterations.append(iteration_result)

            if best_result is None or average_score > best_result.average_score:
                best_result = iteration_result

            logging.info(
                "Средний балл итерации %d: %.2f (цель %.2f)",
                iteration,
                average_score,
                self.target_score,
            )

            if average_score >= self.target_score:
                logging.info("Достигнута целевая оценка, оптимизация завершена.")
                break

            feedback_lines: List[str] = []
            for scenario in scenario_results:
                feedback_lines.append(
                    f"Сценарий {scenario.scenario_index}: средний балл {scenario.average_score:.1f}"
                )
                feedback_lines.extend(
                    f"  Turn {log.turn_index}: score={log.score:.1f} — {log.feedback}"
                    for log in scenario.turns
                )
            feedback_summary = "\n".join(feedback_lines)
            improvement_payload = self.judge.improve_prompt(
                current_prompt=current_prompt,
                expected_style=self.expected_style,
                feedback_summary=feedback_summary,
                average_score=average_score,
            )
            new_prompt = improvement_payload.get("system_prompt", "").strip()
            reasoning = improvement_payload.get("reasoning", "").strip()
            if not new_prompt:
                raise ValueError("Судья не вернул обновлённый системный промт")

            iteration_result.improvement_reason = reasoning or None
            iteration_result.improved_prompt = new_prompt
            current_prompt = new_prompt
            logging.info("Новый системный промт от судьи подготовлен для следующей итерации.")

        if best_result is None:
            raise RuntimeError("Оптимизация не выполнила ни одной итерации.")

        summary = PromptOptimizationSummary(
            success=best_result.average_score >= self.target_score,
            target_score=self.target_score,
            best_iteration=best_result.iteration,
            best_score=best_result.average_score,
            best_prompt=best_result.system_prompt,
            iterations=iterations,
        )
        return summary

    def _train_model(
        self,
        iteration: int,
        system_prompt: str,
        iteration_dir: Path,
    ) -> TrainingRunResult:
        run_config = dict(self.train_config)
        run_config["persona_description"] = system_prompt

        output_dir = iteration_dir / "trainer"
        adapter_dir = iteration_dir / "lora_adapter"
        run_config["output_dir"] = str(output_dir)
        run_config["adapter_dir"] = str(adapter_dir)

        cli_args = config_to_cli_args(run_config)
        parsed_args = parse_train_args(cli_args)
        logging.info("Запускаю обучение (итерация %d).", iteration)
        return run_training(parsed_args)

    def _evaluate_with_judge(
        self,
        system_prompt: str,
        adapter_dir: Path,
        iteration: int,
        output_dir: Path,
        train_metrics: Optional[Dict[str, Any]] = None,
    ) -> IterationResult:
        adapter_dir = Path(adapter_dir).expanduser().resolve()
        if not adapter_dir.exists():
            raise FileNotFoundError(f"LoRA adapter not found for judge evaluation: {adapter_dir}")

        empty_cuda_cache()
        scenario_results: List[ScenarioResult] = []
        for scenario_index in range(1, self.scenarios_per_iteration + 1):
            scenario_result = self._simulate_dialog(
                scenario_index=scenario_index,
                total_scenarios=self.scenarios_per_iteration,
                system_prompt=system_prompt,
                adapter_dir=adapter_dir,
            )
            scenario_results.append(scenario_result)
            logging.info(
                "Сценарий %d/%d — средний балл: %.2f",
                scenario_index,
                self.scenarios_per_iteration,
                scenario_result.average_score,
            )

        average_score = (
            sum(scenario.average_score for scenario in scenario_results) / max(1, len(scenario_results))
        )
        return IterationResult(
            iteration=iteration,
            system_prompt=system_prompt,
            scenarios=scenario_results,
            average_score=average_score,
            adapter_dir=adapter_dir,
            output_dir=Path(output_dir),
            train_metrics=train_metrics or {},
        )

    def _simulate_dialog(
        self,
        scenario_index: int,
        total_scenarios: int,
        system_prompt: str,
        adapter_dir: Path,
    ) -> ScenarioResult:
        logging.info("---- Сценарий %d/%d: старт ----", scenario_index, total_scenarios)
        clone = CloneResponder(
            model_id=self.model_id,
            adapter_dir=adapter_dir,
            precision=self.clone_settings["precision"],
            trust_remote_code=self.trust_remote_code,
            retriever=self.retriever,
            rag_top_k=self.clone_settings.get("rag_top_k", 4),
            vl_backend=self.vl_backend,
        )
        history: List[Dict[str, Any]] = []
        turns: List[TurnLog] = []
        for turn_idx in range(1, self.turns_per_dialog + 1):
            judge_question = self.judge.ask_question(history, self.expected_style)
            history.append({"role": "user", "content": judge_question})
            logging.info("Scenario %d Turn %d — судья: %s", scenario_index, turn_idx, judge_question)

            clone_answer = clone.generate(
                system_prompt=system_prompt,
                history=history,
                max_new_tokens=self.clone_settings["max_new_tokens"],
                temperature=self.clone_settings["temperature"],
                top_p=self.clone_settings["top_p"],
                top_k=self.clone_settings["sample_top_k"],
                do_sample=self.clone_settings["do_sample"],
            )
            history.append({"role": "assistant", "content": clone_answer})
            logging.info("Scenario %d Turn %d — клон: %s", scenario_index, turn_idx, clone_answer)

            evaluation = self.judge.evaluate_turn(history, self.expected_style)
            score = float(evaluation.get("score", 0.0))
            feedback = str(evaluation.get("feedback", "")).strip()
            logging.info(
                "Scenario %d Turn %d — оценка: %.2f | %s",
                scenario_index,
                turn_idx,
                score,
                feedback,
            )

            turn_log = TurnLog(
                turn_index=turn_idx,
                judge_question=judge_question,
                clone_answer=clone_answer,
                score=score,
                feedback=feedback,
                raw_evaluation=json.dumps(evaluation, ensure_ascii=False),
            )
            turns.append(turn_log)

        clone.shutdown()
        average_score = sum(t.score for t in turns) / max(1, len(turns))
        logging.info(
            "---- Сценарий %d/%d завершён. Средний балл: %.2f ----",
            scenario_index,
            total_scenarios,
            average_score,
        )
        return ScenarioResult(scenario_index=scenario_index, turns=turns, average_score=average_score)

    def _write_iteration_artifacts(self, iteration_dir: Path, result: IterationResult) -> None:
        data = iteration_to_dict(result)
        (iteration_dir / "iteration_log.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (iteration_dir / "system_prompt.txt").write_text(result.system_prompt, encoding="utf-8")
        if result.improved_prompt:
            (iteration_dir / "next_system_prompt.txt").write_text(result.improved_prompt, encoding="utf-8")

        for scenario in result.scenarios:
            scenario_dir = iteration_dir / f"scenario_{scenario.scenario_index:02d}"
            scenario_dir.mkdir(parents=True, exist_ok=True)
            (scenario_dir / "scenario_log.json").write_text(
                json.dumps(scenario_to_dict(scenario), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            transcript_lines: List[str] = []
            for turn in scenario.turns:
                transcript_lines.append(f"Judge: {turn.judge_question}")
                transcript_lines.append(f"Clone: {turn.clone_answer}")
                transcript_lines.append(f"Score: {turn.score:.1f} | {turn.feedback}")
                transcript_lines.append("")
            (scenario_dir / "transcript.txt").write_text(
                "\n".join(transcript_lines).strip(),
                encoding="utf-8",
            )

    def run_judge_only(self, adapter_dir: Path, system_prompt: Optional[str] = None) -> PromptOptimizationSummary:
        self.experiment_root.mkdir(parents=True, exist_ok=True)
        system_prompt = system_prompt or self.initial_prompt
        adapter_dir = Path(adapter_dir).expanduser().resolve()
        evaluation_root = self.experiment_root / "iteration_00"
        evaluation_root.mkdir(parents=True, exist_ok=True)

        iteration_result = self._evaluate_with_judge(
            system_prompt=system_prompt,
            adapter_dir=adapter_dir,
            iteration=0,
            output_dir=adapter_dir.parent,
            train_metrics={},
        )
        self._write_iteration_artifacts(evaluation_root, iteration_result)
        logging.info(
            "Средний балл проверки: %.2f (цель %.2f)",
            iteration_result.average_score,
            self.target_score,
        )

        summary = PromptOptimizationSummary(
            success=iteration_result.average_score >= self.target_score,
            target_score=self.target_score,
            best_iteration=iteration_result.iteration,
            best_score=iteration_result.average_score,
            best_prompt=system_prompt,
            iterations=[iteration_result],
        )
        return summary


def turn_to_dict(turn: TurnLog) -> Dict[str, Any]:
    return {
        "turn_index": turn.turn_index,
        "judge_question": turn.judge_question,
        "clone_answer": turn.clone_answer,
        "score": turn.score,
        "feedback": turn.feedback,
        "raw_evaluation": turn.raw_evaluation,
    }


def iteration_to_dict(iteration: IterationResult) -> Dict[str, Any]:
    return {
        "iteration": iteration.iteration,
        "system_prompt": iteration.system_prompt,
        "average_score": iteration.average_score,
        "scenarios": [scenario_to_dict(s) for s in iteration.scenarios],
        "adapter_dir": str(iteration.adapter_dir),
        "output_dir": str(iteration.output_dir),
        "train_metrics": iteration.train_metrics,
        "improvement_reason": iteration.improvement_reason,
        "improved_prompt": iteration.improved_prompt,
    }


def scenario_to_dict(scenario: ScenarioResult) -> Dict[str, Any]:
    return {
        "scenario_index": scenario.scenario_index,
        "average_score": scenario.average_score,
        "turns": [turn_to_dict(t) for t in scenario.turns],
    }


def summary_to_dict(summary: PromptOptimizationSummary) -> Dict[str, Any]:
    return {
        "success": summary.success,
        "target_score": summary.target_score,
        "best_iteration": summary.best_iteration,
        "best_score": summary.best_score,
        "best_prompt": summary.best_prompt,
        "iterations": [iteration_to_dict(it) for it in summary.iterations],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Автоматический подбор системного промта после обучения QLoRA.")
    parser.add_argument("--train-config", type=Path, required=True, help="JSON-файл с аргументами для train_qlora.")
    parser.add_argument(
        "--experiment-root",
        type=Path,
        default=Path("outputs/prompt_optimization"),
        help="Каталог для артефактов каждой итерации.",
    )
    parser.add_argument("--initial-system-prompt", help="Начальный системный промт (строка).")
    parser.add_argument("--initial-system-prompt-file", type=Path, help="Файл с исходным промтом.")
    parser.add_argument("--expected-style", help="Целевой стиль для оценки судьи.")
    parser.add_argument("--expected-style-file", type=Path, help="Файл с описанием стиля.")
    parser.add_argument("--target-score", type=float, default=85.0, help="Необходимый средний балл для остановки.")
    parser.add_argument("--max-iterations", type=int, default=5, help="Максимум итераций оптимизации.")
    parser.add_argument("--turns-per-dialog", type=int, default=5, help="Сколько ходов ведёт судья за итерацию.")
    parser.add_argument(
        "--scenarios-per-iteration",
        type=int,
        default=1,
        help="Сколько независимых диалогов судья ведёт за одну итерацию обучения.",
    )
    parser.add_argument(
        "--judge-only",
        action="store_true",
        help="Запустить только проверку готовой модели судьёй без повторного обучения.",
    )
    parser.add_argument(
        "--judge-only-adapter",
        type=Path,
        default=None,
        help="Путь к LoRA-адаптеру для режима --judge-only. По умолчанию используется adapter_dir из train-config.",
    )

    parser.add_argument("--judge-base-url", required=True, help="Базовый URL прокси Gonka/OpenAI совместимого API.")
    parser.add_argument("--judge-model", required=True, help="ID модели судьи, например Qwen/Qwen3-235B-A22B-Instruct-2507-FP8.")
    parser.add_argument("--judge-api-key", default="not-needed", help="Ключ API для судьи, если требуется.")
    parser.add_argument("--judge-temperature", type=float, default=0.7, help="Температура генерации вопросов судьёй.")

    parser.add_argument("--clone-max-new-tokens", type=int, default=512, help="Максимум новых токенов для клона.")
    parser.add_argument("--clone-temperature", type=float, default=0.8, help="Температура сэмплинга клона.")
    parser.add_argument("--clone-top-p", type=float, default=0.9)
    parser.add_argument("--clone-top-k", type=int, default=40)
    parser.add_argument("--clone-greedy", action="store_true", help="Отключить сэмплирование (детерминированный ответ).")
    parser.add_argument(
        "--clone-precision",
        choices=["4bit", "fp16", "fp32"],
        default="4bit",
        help="Режим загрузки модели клона для оценки.",
    )
    parser.add_argument(
        "--rag-index-dir",
        type=Path,
        default=None,
        help="Каталог с RAG-индексом (embeddings.npy + records.jsonl). Если не указан — RAG отключён.",
    )
    parser.add_argument(
        "--rag-embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Модель эмбеддингов для поиска по RAG-индексу.",
    )
    parser.add_argument(
        "--rag-top-k",
        type=int,
        default=4,
        help="Сколько чанков знаний подмешивать на каждый ответ клона.",
    )

    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    train_config = load_train_config(args.train_config)

    initial_prompt = ensure_prompt(
        resolve_text_arg(args.initial_system_prompt, args.initial_system_prompt_file),
        train_config.get("persona_description"),
        "Начальный системный промт",
    )
    expected_style = ensure_prompt(
        resolve_text_arg(args.expected_style, args.expected_style_file),
        initial_prompt,
        "Целевой стиль",
    )

    rag_retriever: Optional[KnowledgeRetriever] = None
    if args.rag_index_dir is not None:
        rag_retriever = KnowledgeRetriever(
            index_dir=args.rag_index_dir,
            embedding_model=args.rag_embedding_model,
        )

    judge_client = JudgeClient(
        base_url=args.judge_base_url,
        model=args.judge_model,
        api_key=args.judge_api_key,
        temperature=args.judge_temperature,
        retriever=rag_retriever,
        rag_top_k=args.rag_top_k,
    )

    clone_settings = {
        "precision": args.clone_precision,
        "max_new_tokens": args.clone_max_new_tokens,
        "temperature": args.clone_temperature,
        "top_p": args.clone_top_p,
        "sample_top_k": args.clone_top_k,
        "do_sample": not args.clone_greedy,
        "rag_top_k": args.rag_top_k,
    }

    runner = PromptOptimizationRunner(
        train_config=train_config,
        initial_prompt=initial_prompt,
        expected_style=expected_style,
        judge_client=judge_client,
        experiment_root=args.experiment_root,
        target_score=args.target_score,
        max_iterations=args.max_iterations,
        turns_per_dialog=args.turns_per_dialog,
        scenarios_per_iteration=args.scenarios_per_iteration,
        clone_settings=clone_settings,
        retriever=rag_retriever,
    )

    if args.judge_only:
        adapter_path = args.judge_only_adapter or train_config.get("adapter_dir")
        if not adapter_path:
            raise ValueError(
                "Не указан путь к адаптеру для режима --judge-only. "
                "Передайте --judge-only-adapter или добавьте adapter_dir в train_config."
            )
        adapter_dir = Path(adapter_path).expanduser().resolve()
        summary = runner.run_judge_only(adapter_dir=adapter_dir, system_prompt=initial_prompt)
    else:
        summary = runner.run()

    report_path = args.experiment_root / "prompt_optimization_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(summary_to_dict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if summary.success:
        logging.info(
            "Оптимизация завершена успешно на итерации %d с баллом %.2f.",
            summary.best_iteration,
            summary.best_score,
        )
    else:
        logging.warning(
            "Целевой балл %.2f не достигнут. Лучший результат %.2f (итерация %d).",
            summary.target_score,
            summary.best_score,
            summary.best_iteration,
        )

    logging.info("Лучший промт сохранён в %s", args.experiment_root / f"iteration_{summary.best_iteration:02d}" / "system_prompt.txt")


if __name__ == "__main__":
    main()
