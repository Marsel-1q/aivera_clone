# AI Clone Mini‑MVP

Мини‑платформа для создания «цифрового клона»: сбор пользовательских данных, подготовка датасета и дообучение QLoRA. Проект переведён на **Pure Parsing Pipeline** — минимум магии, максимум прозрачности:

- единственный CLI в `dataset_pipeline/cli.py` агрегирует все источники;
- новый стек парсеров (`parsers/`) охватывает TXT/HTML/JSON, изображения и PDF/DOCX через Qwen2‑VL OCR;
- multi-turn пары формируются в одном месте (`processing/dialogue_builder.py`);
- убраны все вторичные шаги (DPO, стилистика, LLM-аугментация, эмоции/тон).

## Структура репозитория

```
dataset_pipeline/
  core/          # схемы, утилиты, валидаторы
  parsers/       # rule-based + VLM + hybrid router
  processing/    # cleaning, dialogue builder, форматирование
  cli.py         # Pure Parsing Pipeline
  requirements.txt
train_qlora.py   # QLoRA fine-tuning (мультимодальные модели)
rag/             # вспомогательные утилиты для RAG индекса
md_files/        # архитектура, инструкции
```

## Подготовка окружения

```bash
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip

# библиотека дообучения
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install transformers datasets peft bitsandbytes trl accelerate tensorboard pillow

# зависимости для Pure Parsing Pipeline
pip install -r dataset_pipeline/requirements.txt
```

> Qwen2-VL OCR скачивается из Hugging Face при первом запуске, поэтому убедитесь, что установлены `transformers`, `torch` и выполнен `huggingface-cli login` с токеном, имеющим доступ к модели.

Авторизация на Hugging Face:

```bash
huggingface-cli login
```

## Pure Parsing Pipeline

1. **Соберите данные** в `data/raw`: экспорты чатов (`.txt`, `.html`, `.jsonl`), скриншоты (`.png`, `.jpg`), документы (`.pdf`, `.docx`, `.md`, `.json`) и любые другие поддерживаемые форматы.
2. **Запустите CLI**:

```bash
python -m dataset_pipeline.cli \
  --inputs data/raw \
  --output-dir data/processed_dataset \
  --persona koder_marsel \
  --persona-aliases Марсель Marsel \
  --eval-split 0.1 \
  --format huggingface \
  --chunk-size 400 \
  --chunk-overlap 80 \
  --enable-vlm \
  --prefer-vlm
```

### Параметры CLI

| Флаг | Описание |
|------|----------|
| `--inputs` | Путь/пути к исходным данным (файлы или каталоги). |
| `--output-dir` | Куда сохранить готовый датасет. |
| `--persona`, `--persona-aliases` | Идентификаторы, по которым ассистент распознаётся в переписках. |
| `--eval-split` | Доля валидации (0–1). По умолчанию 0.1 → 90/10. |
| `--format` | Формат обучающих JSONL: `huggingface`, `sharegpt` или `instruct`. |
| `--chunk-size` / `--chunk-overlap` | Размер и overlap при нарезке знаний на чанки (в словах). |
| `--enable-vlm` / `--disable-vlm` | Включить/выключить Qwen2-VL OCR для изображений/сканов. |
| `--prefer-vlm` | Гонять даже текстовые файлы через VLM (медленнее, но единообразно). |
| `--vlm-model` | ID модели Qwen OCR (по умолчанию `prithivMLmods/Qwen2-VL-OCR-2B-Instruct`). |

### Что делает пайплайн

1. **Smart Router** (`parsers/router.py`) решает, какой парсер применить к файлу:
   - TXT/HTML/JSON/JSONL → rule-based (`parsers/rule_based.py`);
   - PDF/DOCX → гибрид (текстовый парсинг + OCR-фоллбэк);
   - изображения → Qwen2-VL OCR (`parsers/vlm_parser.py`).
2. Каждый парсер возвращает унифицированный `ParsedDocument` (диалог или knowledge).
3. **Cleaning** (`processing/cleaning.py`) нормализует текст, удаляет стоп-фразы, дубликаты.
4. **Dialogue Builder** (`processing/dialogue_builder.py`) группирует сообщения по диалогам и создаёт multi-turn пары: весь диалог до текущего ответа ассистента упакован в один sample.
5. **Knowledge Builder** (часть CLI) режет документы на чанки через `chunk_text`.
6. Валидация (`core/validators.py`) фильтрует слишком короткие/пустые примеры.
7. CLI пишет файлы:
   - `train.jsonl` — обучающая выборка;
   - `eval.jsonl` — валидация;
   - `knowledge.jsonl` — знания/факты;
   - `manifest.json` — конфигурация запуска и статистика.

> Если Qwen2-VL модель недоступна (например, нет токена Hugging Face), запустите CLI с `--disable-vlm` — изображения будут пропущены, но текстовые документы обработаются.

## Обучение модели (QLoRA)

После подготовки датасета запустите дообучение мультимодальной модели:

```bash
python train_qlora.py \
  --train-file data/processed_dataset/train.jsonl \
  --eval-file data/processed_dataset/eval.jsonl \
  --knowledge-file data/processed_dataset/knowledge.jsonl \
  --model-id Qwen/Qwen2.5-VL-7B-Instruct \
  --epochs 3 \
  --batch-size 1 \
  --grad-accum 8 \
  --learning-rate 1e-5 \
  --use-peft \
  --output-dir outputs/qwen25_vl
```

Ключевые аргументы:
- `--train-file`/`--eval-file` — указывают на новые `train.jsonl` и `eval.jsonl`;
- `--knowledge-file` — необязателен, но пригодится для смешивания фактов;
- `--persona-name`/`--persona-description` — задают системное сообщение;
- стандартные параметры QLoRA (rank, target modules, fp16/bf16 и т.д.) уже подключены.

## Типовой рабочий процесс

1. **Сбор данных** → обновление `data/raw`.
2. **Первый прогон Pure Parsing Pipeline** — проверка `manifest.json`, просмотр первых строк `train.jsonl` и `knowledge.jsonl`.
3. **При необходимости** повторный запуск с другими алиасами, фильтрами или форматами (`--format sharegpt` для ShareGPT-style обучающих наборов).
4. **Запуск QLoRA** (`train_qlora.py`) с новыми файлами.
5. **Оценка модели**: inference в ноутбуке/скрипте, проверка мультимодальных сценариев.
6. **RAG (опционально)**: собрать индекс из `knowledge.jsonl` через `rag/index_builder.py`.
7. **Отладка OCR**: для визуальных источников проверяйте `other.jsonl` — туда пайплайн сохраняет текст, извлечённый Qwen2-VL до дополнительной обработки.

## Практические заметки

- **Форматы вывода.** `--format huggingface` сохраняет массив `messages` (роль + текст), `sharegpt` — `{"conversations": [...]}`, `instruct` — `{"instruction": "...", "response": "..."}`. Менять формат можно без повторного парсинга, переупаковав `train.jsonl`.
- **Qwen2-VL OCR.** Используем Hugging Face pipeline `image-text-to-text`; на вход кладём изображение и инструкцию «транскрибировать весь текст». Полученный plain text дальше обрабатывается rule-based парсером, поэтому структура диалога сохраняется.
- **Гибкий валидатор.** Пороговые значения (минимальное количество слов, стоп-фразы) настраиваются централизованно в `processing/cleaning.py` и `core/validators.py`.
- **Расширяемость.** Для новых форматов добавьте парсер в `parsers/`, зарегистрируйте его в `ParserRouter`, и он автоматически попадёт в общий рабочий поток.

## Частые проблемы

| Симптом | Решение |
|---------|---------|
| HF VLM модель не скачивается | Проверьте подключение к Hugging Face и наличие прав на `prithivMLmods/Qwen2-VL-OCR-2B-Instruct`; при необходимости запустите `huggingface-cli login`. |
| OCR возвращает пустые строки | Проверьте, что модель Qwen2-VL скачалась (нужен `huggingface-cli login`) и хватает памяти/GPU для инференса. |
| Слишком мало валидационных примеров | Уменьшите `--eval-split` или добавьте больше диалогов; при единичных сэмплах CLI автоматически переносит последний train sample в eval. |
| `train_qlora.py` не видит eval | Передайте `--eval-file path/to/eval.jsonl` — значение уже совпадает с выходом пайплайна. |
| CUDA OOM | Уменьшите `--batch-size`, `--grad-accum`, `--max-seq-length` или перейдите на более компактную модель. |

## Дополнительно

- В `md_files/dataset_update.md` описана финальная архитектура Pure Parsing Pipeline.
- `rag/index_builder.py` строит векторный индекс из `knowledge.jsonl` (нужен `datasets` и `sentence-transformers`).
- Telegram-бот с RAG и памятью Redis описан в `md_files/telegram.md`.

Проект развивается итеративно: сначала собираем чистый и воспроизводимый датасет, затем адаптируем мультимодальную модель под конкретную персону. Pure Parsing Pipeline упрощает этот цикл и делает добавление новых данных или форматов прямолинейным.
