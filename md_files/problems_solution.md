## Пересмотренный анализ (для 1700 примеров)

### ✅ **Что теперь НЕ является проблемой:**

1. **Размер датасета** — 1700 достаточно для обучения персонального стиля.[^2][^3][^1]
2. **Overfitting риск** — снижен (хотя всё ещё нужно следить за eval_loss).[^4][^1]

### 🔴 **Основные проблемы (актуальные для 1700 примеров):**

#### **1. Качество данных из Telegram (критично!)**

Экспорт чатов из Telegram часто содержит:

- **Короткие реплики** ("ок", "спс", "👍") — не несут смысла для обучения.[^5][^6]
- **Обрывки контекста** — модель видит ответ без вопроса или наоборот.[^6][^5]
- **Технический мусор** — timestamp, system messages, forwards.[^5][^6]
- **Несбалансированные пары** — много коротких ответов, мало развёрнутых.[^7][^5]

**Что делать:**

```python
# Добавь фильтрацию в dataset_pipeline.py:
def is_valid_pair(prompt, completion):
    # Минимальная длина
    if len(prompt.split()) < 3 or len(completion.split()) < 5:
        return False
    # Проверка на мусор
    trash_patterns = ['ok', 'ок', 'спасибо', '👍', 'хорошо', '+']
    if completion.lower().strip() in trash_patterns:
        return False
    return True
```


***

#### **2. Кастомный instruction format vs native chat template**

Твой код использует:

```python
### Instruction:
{prompt}
### Response:
{completion}
```

**Проблема для Qwen2.5:**

- Qwen2.5-7B-Instruct обучалась на **ChatML format**:[^8][^9][^10]

```
<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{user_message}<|im_end|>
<|im_start|>assistant
{assistant_response}<|im_end|>
```

- Когда ты используешь свой формат (\#\#\# Instruction / \#\#\# Response), модель **теряет alignment** с предобученной структурой.[^9][^10][^8]
- Это объясняет, почему модель "говорит о другом" — она не понимает, где начинается/заканчивается твой промпт.[^10][^8][^9]

**Решение:**

```python
# Замени build_instruction_text() на:
def format_with_native_template(example):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": example["prompt"]},
        {"role": "assistant", "content": example["completion"]}
    ]
    # Используй native chat template модели
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False
    )
    return {"text": text}
```

**Почему это важно:**

- Исследования показывают, что **правильный chat template** даёт +10-15% accuracy на instruction tasks.[^8][^9][^10]
- Модель "понимает" структуру диалога и генерирует ответы в нужном месте.[^9][^10][^8]

***

#### **3. Слишком много target_modules для conversational task**

```python
target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "up_proj", "down_proj", "gate_proj"]
```

**Для 1700 примеров:**

- Обучение **MLP layers** (up_proj, down_proj, gate_proj) нужно для **reasoning/знаний**, но не для **стиля общения**.[^11][^12][^10]
- Для персонального клона достаточно **только attention**: `["q_proj", "k_proj", "v_proj", "o_proj"]`.[^12][^10][^11]

**Почему:**

- Attention отвечает за "как отвечать" (стиль, tone).[^11][^12]
- MLP отвечает за "что отвечать" (факты, знания).[^12][^11]
- Обучение MLP на чатах может **испортить** базовые знания модели.[^10][^11][^12]

***

#### **4. Learning rate слишком высок для conversational fine-tuning**

```python
learning_rate=2e-4
```

**Проблема:**

- 2e-4 — это стандарт для **instruction tuning с нуля**.[^8][^9][^10]
- Для **style adaptation** на уже инструкционной модели (Qwen2.5-7B-**Instruct**) лучше использовать **1e-4 или даже 5e-5**.[^3][^1][^10]

**Почему:**

- Высокий LR может "сломать" базовые capabilities модели.[^1][^10]
- Модель начинает "забывать", как отвечать на общие вопросы, и фокусируется только на твоих паттернах.[^1][^10]

***

#### **5. Evaluation strategy = "epoch" (недостаточный контроль)**

При 1700 примерах с batch_size=4 и grad_accum=4:

- Эффективный batch = 16
- Steps per epoch = 1700 / 16 ≈ **106 steps**

**Проблема:**

- Ты видишь метрики только 1 раз в эпоху (106 шагов).[^3][^1]
- Если модель начнёт переобучаться на шаге 50 — ты узнаешь об этом только на шаге 106.[^3][^1]

**Решение:**

```python
evaluation_strategy="steps",
eval_steps=50,  # проверка каждые 50 шагов
```


***

#### **6. Отсутствие early stopping**

Без early stopping модель продолжает обучаться, даже если eval_loss растёт.[^4][^1][^3]

**Добавь:**

```python
from transformers import EarlyStoppingCallback

callbacks=[
    EarlyStoppingCallback(
        early_stopping_patience=3,  # остановка после 3 эпох без улучшения
        early_stopping_threshold=0.01
    )
]
```


***

## 🚀 **Конкретный план улучшений (для 1700 примеров)**

### **Приоритет 1: Исправь chat template (самое важное!)**

```python
# В train_qlora.py замени _format_with_context():
def _format_with_context(row: dict) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Добавь историю если есть
    if row.get("history"):
        for turn in row["history"]:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})
    
    # Текущий вопрос-ответ
    messages.append({"role": "user", "content": row["prompt"]})
    messages.append({"role": "assistant", "content": row["completion"]})
    
    # Используй native template
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False
    )
    return {"text": text}
```


***

### **Приоритет 2: Очисти датасет**

Добавь в `dataset_pipeline.py`:

```python
def clean_telegram_data(pairs):
    cleaned = []
    for p in pairs:
        # Фильтруй короткие/мусорные
        if len(p["completion"].split()) < 5:
            continue
        # Удаляй эмодзи-only ответы
        if all(c in '👍👎😊😂🔥💯' for c in p["completion"].strip()):
            continue
        cleaned.append(p)
    return cleaned
```


***

### **Приоритет 3: Снизь LR и уменьши target_modules**

```bash
!python train_qlora.py \
  --model-id Qwen/Qwen2.5-7B-Instruct \
  --epochs 5 \
  --batch-size 4 \
  --grad-accum 4 \
  --learning-rate 1e-4  # вместо 2e-4
```

В коде:

```python
target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]  # только attention
```


***

### **Приоритет 4: Добавь eval_steps + early stopping**

```python
training_args = TrainingArguments(
    ...
    evaluation_strategy="steps",
    eval_steps=50,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    ...
)

trainer = SFTTrainer(
    ...
    callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
)
```


***

## 📊 **Ожидаемые результаты после улучшений**

С учётом 1700 примеров + исправления выше:

- **Eval loss должен упасть до 1.5-2.0** (сейчас 2.8).[^2][^1]
- **Mean token accuracy: 0.55-0.65** (сейчас 0.44).[^2][^1]
- **Качественно**: модель будет отвечать в твоём стиле на 70-80% вопросов.[^1][^2]

***

## 🎯 **Почему модель сейчас "говорит о другом"?**

Скорее всего комбинация:

1. **Неправильный chat template** → модель не понимает структуру твоих промптов (80% вероятность).[^9][^10][^8]
2. **Высокий LR** → модель "переобучилась" и потеряла базовые навыки (15% вероятность).[^10][^1]
3. **Шум в данных** → много коротких/бессмысленных пар из Telegram (5% вероятность).[^6][^5]

***

**Начни с исправления chat template (\#1) — это даст самый большой эффект!** Если после этого всё ещё плохо — применяй остальные улучшения по порядку.


[^1]: https://www.sapien.io/blog/strategies-for-fine-tuning-llms-on-small-datasets

[^2]: https://arxiv.org/html/2412.13337v1

[^3]: https://dialzara.com/blog/fine-tuning-llms-with-small-data-guide

[^4]: https://milvus.io/ai-quick-reference/how-do-you-handle-overfitting-in-small-datasets

[^5]: https://www.reddit.com/r/OpenAI/comments/1al8eol/how_to_detect_bad_data_in_your_instruction_tuning/

[^6]: https://cleanlab.ai/blog/filter-llm-tuning-data/

[^7]: https://arxiv.org/pdf/2311.13246.pdf

[^8]: https://www.philschmid.de/fine-tune-llms-in-2025

[^9]: https://collabnix.com/how-to-fine-tune-llm-and-use-it-with-ollama-a-complete-guide-for-2025/

[^10]: https://machinelearningmastery.com/the-machine-learning-practitioners-guide-to-fine-tuning-language-models/

[^11]: https://watercrawl.dev/blog/LoRA-and-QLoRA

[^12]: https://www.digitaldividedata.com/blog/ai-fine-tuning-techniques-lora-qlora-and-adapters

