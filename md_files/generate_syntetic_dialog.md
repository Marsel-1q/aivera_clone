## 1. Структура каталогов

```
startup/
├── data/
│   ├── raw/              # Реальные/примерные датасеты (html, json, ...  любые источники)
│   ├── generated/        # Промежуточные и финальные json/jsonl с синтетикой
├──syntetic-dialog/
    ├── config.py             # Константы, настройка ролей, системные инсты, опции генерации
    ├── generator.py          # Главный скрипт (всё в одном файле). 
    └── requirements.txt
```

***

## 2. Обзор архитектуры скрипта

**Основные этапы:**

1. **DataLoader** — загрузка и парсинг примеров из `data/raw/`.
   - Примеры преобразуются при необходимости в нужный диалоговый вид для подачи LLM.

2. **PromptBuilder** — создание системного промпта с максимально подробным ТЗ, показывающим:
   - фрагменты реальных примеров в нужном формате;
   - требования к длине, развёрнутости, структуре, маркерам ролей;
   - формат вывода: *всё диалоговое взаимодействие в одном поле prompt (user/assistant/метки), последний вопрос в истории — completion как ответ*, массив messages для структурности.

3. **DialogueGenerator** — генерация через Qwen (через Gonka AI по прокси).
   - Автоматически вызывает LLM с промптом;
   - Ждёт возврат валидного JSON: `prompt`, `completion`, `messages`, `metadata`.
   - Парсит результат как словарь.

4. **DialogueValidator**
   - Проверяет формат: наличие ролей, достаточную длину, presence completion, валидность массива messages;
   - Проверяет семантику: last user -> completion by assistant.

5. **DataNormalizer**
   - Чистит и нормализует prompt: убирает лишние пробелы, унифицирует кавычки, контролирует переводы строк и маркеры ролей;
   - Реорганизует массив messages (только нужные поля, правильный порядок);
   - metadata очищается и агрегируется;
   - Сохраняет в итоговый jsonl: максимально плоский формат, валидный для обучения.

6. **Main Pipeline**
   - Спрашивает у пользователя, какую роль генерировать (crypto seller, sneakers seller, it sales и др.);
   - Загружает примеры из raw;
   - Генерирует синтетический датасет нужного размера;
   - Валидирует и чистит;
   - Сохраняет в `data/generated/synthetic_{role}_{timestamp}.jsonl` для fine-tune,
   - логи и промежуточные данные — отдельно в json.

***

## 3. Пример системного промпта для LLM

(Часть кода, которая динамически строится в PromptBuilder)

```python
SYSTEM_PROMPT = f"""
Ты — генератор реалистичных длинных диалогов для fine-tuning диалоговой модели. Генерируй долгий, развёрнутый диалог между {role_description} и клиентом именно в таком формате, где:
- Вся история (от первого сообщения до последнего) идёт в одном поле "prompt". Каждый репликант отмечен (например: "user:", "assistant:", имя/ник, если это важно).
- Последний вопрос или запрос клиента требуется выделить как "completion": твой ответ (assistant).
- messages: массив с ролью, текстом, порядком.
- Пример ниже.
- Формат возврата — только валидный JSON.

Параметры:
- Продолжительность диалога: несколько дней, в истории могут быть паузы.
- Не менее 40-60 сообщений в истории (prompt).
- Диалог живой, перемежаются темы, есть off-topic, есть обычные вопросы.
- Стиль/инструкции персонажа: {role_specific_instructions}

Пример:

{{
  "prompt": "user: Привет!\nassistant: Добрый день! Чем могу помочь?\nuser: ..."
  "completion": "Ваш заказ оформлен! Оплата — картой, доставка 3-5 дней.",
  "messages": [
     { "role": "user", "content": "...", "order": 0}, ...
  ],
  "metadata": { "...": "..." }
}}

Сгенерируй диалог в этом формате для роли "{role_type}".
"""
```

***

## Пример generate.py

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI
import random

# --------- КОНФИГУРАЦИЯ ----------
class Config:
    BASE_URL = "http://localhost:8080/v1"  # Gonka AI proxy endpoint
    MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
    RAW_DATA_PATH = Path("data/raw")
    OUTPUT_PATH = Path("data/generated")
    NUM_CONVERSATIONS = 150
    ROLE = "crypto_seller"
    TEMPERATURE = 0.95
    MAX_TOKENS = 4000

# --------- ROLE INSTRUCTIONS ----------
ROLE_INSTRUCTIONS = {
    "crypto_seller": "Ты — продавец онлайн-курса по криптовалютам. Эксперт в DeFi, trading, блокчейне. Старайся убеждать, работать с возражениями, использовать примеры, делать диалоги живыми и дружелюбными, вставляй крипто-термины умеренно.",
    "sneakers_seller": "Ты — ресселлер кроссовок. Разбираешься в моделях, быстро отвечаешь, пишешь неформально, при необходимости присылай фото/размеры, расскажи про доставку.",
    "it_sales": "Ты — сотрудник IT-компании, консультируешь по интеграции IT-решений. Примеры, цифры, бизнес-подход, профессиональный стиль, но не сухой."
}

# --------- DATA LOADER ----------
def load_examples(path: Path) -> List[str]:
    examples = []
    for file in path.glob("*"):
        if file.suffix == ".json":
            with open(file, "r", encoding="utf-8") as f:
                examples.append(f.read())
        elif file.suffix == ".html":
            with open(file, "r", encoding="utf-8") as f:
                examples.append(f.read())
    return examples

# --------- PROMPT BUILDER ----------
def build_system_prompt(role: str, role_instruction: str, example_dialogue: str = "") -> str:
    return f"""
Сгенерируй длинный реалистичный диалог для обучения AI-ассистента-{role}.
Формат вывода — ТОЛЬКО валидный JSON следующего вида:
{{
  "prompt": "user: Привет!\nassistant: Добрый день! Чем могу помочь?\n...",
  "completion": "Ваш заказ оформлен. Оплата — картой, доставка 3-5 дней.",
  "messages": [
     {{ "role": "user", "content": "...", "order": 0 }},
     {{ "role": "assistant", "content": "...", "order": 1 }}
  ],
  "metadata": {{
     "role_type": "{role}",
     "generated": true
  }}
}}

Требования:
- Диалог длинный, не менее 40 сообщений, длится несколько дней, паузы допустимы.
- Каждый спикер: user/assistant или осмысленные имена ("Сергей:", "Алексей:") — отмечай в промпте.
- В конце prompt — вопрос/сообщение, на который нужно дать ответ ("completion").
- Dialoque целостный, роли чередуются, оффтоп разрешён.
- {role_instruction}
- Пример диалога, если нужен, ниже:
{example_dialogue}
Сгенерируй новый, уникальный диалог для выбранной сцены.
"""

# --------- DIALOGUE GENERATOR ----------
class DialogueGenerator:
    def __init__(self):
        self.client = OpenAI(base_url=Config.BASE_URL, api_key="not-needed")

    def generate(self, prompt: str) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model=Config.MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Генерируй диалог в формате выше."}
            ],
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_TOKENS
        )
        content = response.choices[0].message.content.strip()
        # Чистим от markdown-обёртки при необходимости
        if "```
            content = content.split("```json").split("```
        elif "```" in content:
            content = content.split("``````")[0].strip()
        try:
            return json.loads(content)
        except Exception as e:
            print("Ошибка парсинга:", e)
            return None

# --------- NORMALIZER ----------
def normalize_dialogue(d: Dict[str, Any]) -> Dict[str, Any]:
    # Убрать двойные пробелы, привести формат prompt/messages к норме
    d["prompt"] = "\n".join([line.strip() for line in d.get("prompt", "").split("\n") if line.strip()])
    d["completion"] = d.get("completion", "").strip()
    d["messages"] = [
        {
            "role": m.get("role", "user"),
            "content": " ".join((m.get("content") or "").split()),
            "order": m.get("order", idx)
        }
        for idx, m in enumerate(d.get("messages", []))
    ]
    return d

# --------- MAIN PIPELINE ----------
def main():
    os.makedirs(Config.OUTPUT_PATH, exist_ok=True)
    examples = load_examples(Config.RAW_DATA_PATH)
    role_instruction = ROLE_INSTRUCTIONS.get(Config.ROLE, "")
    random_example = random.choice(examples) if examples else ""
    system_prompt = build_system_prompt(Config.ROLE, role_instruction, random_example)

    generator = DialogueGenerator()
    converations = []
    for i in range(Config.NUM_CONVERSATIONS):
        print(f"Диалог {i+1}/{Config.NUM_CONVERSATIONS} ...")
        data = generator.generate(system_prompt)
        if not data or "prompt" not in data or "completion" not in data:
            print("FAIL")
            continue
        data = normalize_dialogue(data)
        converations.append(data)
        # save intermediate
        if i % 10 == 0:
            with open(Config.OUTPUT_PATH / f"synthetic_{Config.ROLE}_intermediate.jsonl", "w", encoding="utf-8") as f:
                for conv in converations:
                    f.write(json.dumps(conv, ensure_ascii=False) + "\n")
        time.sleep(1)

    final_path = Config.OUTPUT_PATH / f"synthetic_{Config.ROLE}.jsonl"
    with open(final_path, "w", encoding="utf-8") as f:
        for conv in converations:
            f.write(json.dumps(conv, ensure_ascii=False) + "\n")
    print(f"Готово! Датасет: {final_path}")

if __name__ == "__main__":
    main()


## 4. Пример инструкции пользователя на старте

```python
python generator.py --role crypto_seller --count 150
```

***

## 5. requirements.txt

```
openai>=1.12.0
```

***

## 6. Главный pipeline (описание этапов)

1. **Запуск:**  
   - Выбор роли генерации: ит-сфера / крипта / ресселлер и тд.
2. **Чтение и анализ примеров (`data/raw`)**
3. **Построение промпта системы с учетом роли/границ/формата**
4. **Генерация диалогов (150шт) через Qwen/LLM (Gonka прокси)**
5. **Пост-обработка:**
   - Валидация, фильтрация битых/коротких диалогов
   - Чистка и нормализация данных (удаление лишних символов, исправление маркеров, лексическая пост-обработка)
6. **Сохранение:**
   - Единственный .jsonl (каждая строка — отдельный диалог: prompt, completion, messages, metadata)
   - Дополнительно — отчёт с логами/валидностью.
7. **Дальнейшая передача в пайплайн обучения**

***

## 7. Пример схемы итоговой записи

```json
{"prompt": "user: ...\nassistant: ...\nuser: ...", "completion": "ответ на последний вопрос", "messages": [{"role": "user", "content": "...", "order": 0}, ...], "metadata": {"role_type": "crypto_seller", "generated": true} }
```

***

**Результат**:  
На выходе вы получаете структурированный .jsonl файл, отлично подходящий для обучения LLM диалоговому стилю с чёткой маркировкой, удобной для парсинга и анализа. Всё максимально автоматизировано и адаптируется к выбранной предметной области.