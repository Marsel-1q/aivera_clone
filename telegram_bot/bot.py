#!/usr/bin/env python3
"""Telegram бот для тестирования цифрового клона с RAG и памятью в Redis."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.client.bot import DefaultBotProperties

import socket

import torch

try:  # Загрузка переменных окружения из .env, если пакет доступен.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - пакет опционален
    pass

from rag.rag_inference import load_model
from rag.retriever import KnowledgeRetriever, RetrievalResult

try:
    from redis.asyncio import Redis as AsyncRedis
except ImportError:  # pragma: no cover - redis необязателен
    AsyncRedis = None

try:
    from fakeredis import FakeAsyncRedis
except ImportError:  # pragma: no cover - fakeredis не обязателен
    FakeAsyncRedis = None

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BotConfig:
    """Конфигурация Telegram-бота."""

    telegram_bot_token: str
    system_prompt: str = (
        "Ты — цифровой клон Били. Держи его стиль: уверенный, тёплый продавец."
        "Общайся в точности как Били. У тебя свой телеграмм магазин по продаже "
        "кроссовок / одежды. Без лишних слов, если чего-то не знаешь — уточни как Били. "
        "Бери цены / размеры и все нужные данные из знаний, сам не выдумывай ничего, "
        "внимательно работай с RAG, если чего-то нет — честно скажи. "
        "Никогда не проси нажимать кнопки для оформления заказа. Не извиняйся как робот: 'Вы действительно правы, я был не прав', не так не извиняйся. Будь в стиле твоего оригинал, даже если ты ошибся, извиняйся как человек как твой оригинал, не более и не менее"
    )
    redis_url: str = "redis://localhost:6379/0"
    redis_namespace: str = "billy-clone"
    redis_ttl_seconds: int = 24 * 60 * 60
    max_history_messages: int = 10  # Храним последние 10 сообщений (5 пар)

    model_id: str = "Qwen/Qwen2.5-7B-Instruct"
    adapter_path: Path = Path("outputs/dpo_adapter")
    load_in_4bit: bool = True
    trust_remote_code: bool = True

    index_dir: Path = Path("data/rag_index")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_top_k: int = 4

    max_new_tokens: int = 512
    temperature: float = 0.83
    sample_top_p: float = 0.92
    sample_top_k: int = 47
    greedy: bool = False

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Собираем параметры из переменных окружения."""

        defaults = cls.__dataclass_fields__  # type: ignore[attr-defined]

        def _as_bool(value: Optional[str], default: bool) -> bool:
            if value is None:
                return default
            return value.lower() in {"1", "true", "yes", "y", "on"}

        def _get_default(field: str) -> Any:
            return defaults[field].default  # type: ignore[index]

        adapter_path = Path(os.getenv("ADAPTER_PATH", "outputs/lora_adapter"))
        index_dir = Path(os.getenv("INDEX_DIR", "data/rag_index"))

        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            system_prompt=os.getenv("SYSTEM_PROMPT", _get_default("system_prompt")),
            redis_url=os.getenv("REDIS_URL", _get_default("redis_url")),
            redis_namespace=os.getenv("REDIS_NAMESPACE", _get_default("redis_namespace")),
            redis_ttl_seconds=int(os.getenv("REDIS_TTL_SECONDS", _get_default("redis_ttl_seconds"))),
            max_history_messages=int(os.getenv("MAX_HISTORY_MESSAGES", _get_default("max_history_messages"))),
            model_id=os.getenv("MODEL_ID", _get_default("model_id")),
            adapter_path=adapter_path,
            load_in_4bit=_as_bool(os.getenv("LOAD_IN_4BIT"), _get_default("load_in_4bit")),
            trust_remote_code=_as_bool(os.getenv("TRUST_REMOTE_CODE"), _get_default("trust_remote_code")),
            index_dir=index_dir,
            embedding_model=os.getenv("EMBEDDING_MODEL", _get_default("embedding_model")),
            rag_top_k=int(os.getenv("RAG_TOP_K", _get_default("rag_top_k"))),
            max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", _get_default("max_new_tokens"))),
            temperature=float(os.getenv("TEMPERATURE", _get_default("temperature"))),
            sample_top_p=float(os.getenv("SAMPLE_TOP_P", _get_default("sample_top_p"))),
            sample_top_k=int(os.getenv("SAMPLE_TOP_K", _get_default("sample_top_k"))),
            greedy=_as_bool(os.getenv("GREEDY"), _get_default("greedy")),
        )


def create_redis_client(redis_url: str) -> tuple[Any, bool]:
    """Возвращает подключение к Redis или его in-memory замену.

    Возвращает кортеж (client, is_real_redis).
    """

    def _check_socket(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            return False

    if AsyncRedis is not None:
        parsed = urlparse(redis_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379

        if _check_socket(host, port):
            logger.info("✅ Используется настоящий Redis (%s:%s)", host, port)
            return AsyncRedis.from_url(redis_url, decode_responses=True), True
        logger.warning(
            "Redis недоступен по адресу %s:%s — переключаемся на FakeRedis, если доступен.",
            host,
            port,
        )

    if FakeAsyncRedis is not None:
        logger.info("⚠️  Используется FakeRedis (in-memory). Данные не сохраняются между перезапусками.")
        return FakeAsyncRedis(decode_responses=True), False

    raise RuntimeError(
        "Redis недоступен, а пакет fakeredis не установлен. "
        "Установите redis-server или добавьте зависимость fakeredis: `pip install fakeredis`."
    )


class ConversationMemory:
    """Управление историей диалога через Redis."""

    def __init__(
        self,
        redis: Any,
        namespace: str,
        max_messages: int,
        ttl_seconds: int,
    ) -> None:
        self.redis = redis
        self.namespace = namespace
        self.max_messages = max_messages
        self.ttl_seconds = ttl_seconds

    def _key(self, user_id: int) -> str:
        return f"{self.namespace}:conversation:{user_id}"

    async def get_history(self, user_id: int) -> List[Dict[str, str]]:
        """Возвращает историю переписки пользователя."""
        raw = await self.redis.get(self._key(user_id))
        if not raw:
            return []
        try:
            payload = json.loads(raw)
            if isinstance(payload, list):
                return [
                    {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
                    for item in payload
                    if isinstance(item, dict)
                ]
        except json.JSONDecodeError:
            logger.warning("Не удалось декодировать историю чата пользователя %s", user_id)
        return []

    async def append_turn(self, user_id: int, user_content: str, assistant_content: str) -> None:
        """Добавляет пару сообщений user/assistant и обрезает историю."""
        history = await self.get_history(user_id)
        history.append({"role": "user", "content": user_content})
        history.append({"role": "assistant", "content": assistant_content})
        if len(history) > self.max_messages:
            history = history[-self.max_messages :]
        await self.redis.set(
            self._key(user_id),
            json.dumps(history, ensure_ascii=False),
            ex=self.ttl_seconds,
        )

    async def clear(self, user_id: int) -> None:
        """Удаляет историю диалога."""
        await self.redis.delete(self._key(user_id))


class RAGService:
    """Обёртка над KnowledgeRetriever для получения релевантных чанков."""

    def __init__(self, index_dir: Path, embedding_model: str, top_k: int) -> None:
        logger.info("Загружаем RAG-индекс из %s", index_dir)
        self.retriever = KnowledgeRetriever(index_dir=index_dir, embedding_model=embedding_model)
        self.top_k = top_k

    def retrieve(self, query: str) -> List[RetrievalResult]:
        if not query.strip():
            return []
        return self.retriever.search(query, k=self.top_k)


class LLMService:
    """Управление генерацией ответов LLM."""

    def __init__(self, config: BotConfig) -> None:
        logger.info("Загружаем модель %s", config.model_id)
        adapter_path = config.adapter_path if config.adapter_path.exists() else None
        self.model, self.tokenizer = load_model(
            model_id=config.model_id,
            adapter_path=adapter_path,
            load_in_4bit=config.load_in_4bit,
            trust_remote_code=config.trust_remote_code,
        )
        self.config = config
        self._generation_lock = asyncio.Lock()
        logger.info("Модель успешно загружена (устройство: %s)", self.model.device)

    def _compose_system_prompt(self, context_snippets: Sequence[RetrievalResult]) -> str:
        if not context_snippets:
            return self.config.system_prompt

        lines = [f"- {item.content}" for item in context_snippets if item.content.strip()]
        if not lines:
            return self.config.system_prompt

        context_block = "\n".join(lines)
        return f"{self.config.system_prompt}\n\nДоступная информация о товарах:\n{context_block}"

    def _build_messages(
        self,
        system_prompt: str,
        history: Sequence[Dict[str, str]],
        user_message: str,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _generate(self, messages: Sequence[Dict[str, str]]) -> str:
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=not self.config.greedy,
                temperature=self.config.temperature if not self.config.greedy else None,
                top_p=self.config.sample_top_p if not self.config.greedy else None,
                top_k=self.config.sample_top_k if not self.config.greedy else None,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output[0][inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()

    async def generate_reply(
        self,
        history: Sequence[Dict[str, str]],
        user_message: str,
        context_snippets: Sequence[RetrievalResult],
    ) -> str:
        """Асинхронная генерация ответа с учётом истории и RAG."""
        system_prompt = self._compose_system_prompt(context_snippets)
        messages = self._build_messages(system_prompt, history, user_message)

        async with self._generation_lock:
            return await asyncio.to_thread(self._generate, messages)


class TelegramCloneBot:
    """Главный класс Telegram-бота."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.bot = Bot(
            token=config.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher()

        self.redis, _ = create_redis_client(config.redis_url)
        self.memory = ConversationMemory(
            redis=self.redis,
            namespace=config.redis_namespace,
            max_messages=config.max_history_messages,
            ttl_seconds=config.redis_ttl_seconds,
        )
        self.rag = RAGService(
            index_dir=config.index_dir,
            embedding_model=config.embedding_model,
            top_k=config.rag_top_k,
        )
        self.llm = LLMService(config)
        self._locks: Dict[int, asyncio.Lock] = {}

        # Регистрация хендлеров
        self.dispatcher.message.register(self.handle_start, CommandStart())
        self.dispatcher.message.register(self.handle_message, F.text)

        # События старта/завершения
        self.dispatcher.startup.register(self.on_startup)
        self.dispatcher.shutdown.register(self.on_shutdown)

    async def on_startup(self) -> None:
        logger.info("Проверяем подключение к Redis: %s", self.config.redis_url)
        try:
            await self.redis.ping()
            logger.info("Redis доступен.")
        except Exception as exc:  # pragma: no cover - зависит от окружения
            logger.error("Не удалось подключиться к Redis: %s", exc)
            raise

    async def on_shutdown(self) -> None:
        logger.info("Корректное завершение работы бота...")
        await self.redis.close()
        await self.bot.session.close()

    async def handle_start(self, message: Message) -> None:
        """Приветственный ответ на /start, очищает историю диалога."""
        user_id = message.from_user.id if message.from_user else message.chat.id
        await self.memory.clear(user_id)
        await message.answer(
            "Привет! Я цифровой клон Били. Задавайте вопросы — подскажу, что есть в наличии "
            "и помогу подобрать нужные размеры."
        )

    async def handle_message(self, message: Message) -> None:
        """Основной обработчик свободного диалога."""
        if not message.from_user:
            logger.debug("Игнорируем сообщение без информации о пользователе: %s", message.message_id)
            return

        user_id = message.from_user.id
        text = (message.text or "").strip()
        if not text:
            await message.answer("Я могу отвечать только на текстовые сообщения.")
            return

        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            try:
                logger.info("Новое сообщение от %s: %s", user_id, text)
                history = await self.memory.get_history(user_id)
                snippets = self.rag.retrieve(text)
                response = await self.llm.generate_reply(
                    history=history,
                    user_message=text,
                    context_snippets=snippets,
                )
                await self.memory.append_turn(user_id, text, response)
                await message.answer(response)
            except Exception as exc:  # pragma: no cover - зависит от инференса
                logger.exception("Ошибка во время обработки сообщения")
                await message.answer("Извини, что-то пошло не так. Попробуй ещё раз позже.")

    async def run(self) -> None:
        """Запускает long polling."""
        await self.dispatcher.start_polling(self.bot, allowed_updates=[])


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = BotConfig.from_env()
    if not config.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN не указан. Задайте его в переменных окружения или в файле .env."
        )
    bot = TelegramCloneBot(config)
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановка бота.")
