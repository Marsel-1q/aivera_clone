# Итоговый План и Архитектура Dataset Pipeline (Final Version)

## 🎯 Концепция

**Pure Parsing Pipeline** — максимально упрощенный, гибкий и эффективный pipeline для подготовки датасетов AI клонов.

**Философия:**
- ✅ Парсинг любых форматов через **Rule-Based + VLM**
- ✅ Минимум кода, максимум функциональности
- ❌ Никакой LLM-аугментации (извлечение знаний из диалогов)
- ❌ Никаких аннотаций (emotions, topics, tone)
- ❌ Никакой стилистики (clustering, preferences)
- ❌ Никакого DPO generation

***

## 📁 Файловая Структура (NEW)

```
dataset_pipeline/
│
├── core/                           # Базовые компоненты
│   ├── __init__.py
│   ├── schemas.py                  # Dataclasses (сохранить без изменений)
│   ├── utils.py                    # Утилиты (сохранить без изменений)
│   └── validators.py               # Валидация датасета (сохранить)
│
├── parsers/                        # Парсеры для разных форматов
│   ├── __init__.py
│   ├── router.py                   # 🆕 Smart routing логика
│   ├── rule_based.py               # 🔄 Миграция из chats.py
│   ├── vlm_parser.py               # 🆕 Qwen2-VL OCR wrapper
│   └── hybrid_parser.py            # 🆕 Rule-based + VLM fallback
│
├── processing/                     # Обработка данных
│   ├── __init__.py
│   ├── cleaning.py                 # ✅ Сохранить из старого кода
│   ├── dialogue_builder.py         # 🆕 Построение prompt-completion пар
│   └── formatting.py               # 🆕 Форматирование для fine-tuning
│
├── cli.py                          # 🔄 Упрощенный CLI (убрать augmentation)
├── requirements.txt                # Dependencies
└── README.md                       # Документация
```

### **Что удаляем:**
- ❌ `annotations.py` — эмоции/топики не нужны
- ❌ `preferences.py` — стилистический анализ не нужен
- ❌ `augment.py` — LLM-аугментация не нужна
- ❌ `knowledge.py` — функционал переносится в parsers

### **Что сохраняем:**
- ✅ `schemas.py` — dataclasses остаются
- ✅ `utils.py` — вспомогательные функции остаются
- ✅ `validators.py` — валидация остается
- ✅ `cleaning.py` — дедупликация и фильтрация остаются

### **Что рефакторим:**
- 🔄 `chats.py` → `parsers/rule_based.py` (переносим всю логику TXT/HTML/JSON/JSONL)
- 🔄 `cli.py` — упрощаем, убираем augmentation опции

***

## 🏗️ Архитектура Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                            │
│  Файлы: TXT, HTML, JSON, JSONL, PNG, JPG, PDF, DOCX          │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                    SMART ROUTER                                │
│  Определяет оптимальный parser для каждого файла               │
│                                                                │
│  Logic:                                                        │
│  • TXT/HTML/JSON/JSONL → Rule-Based Parser                    │
│  • PNG/JPG/Screenshots → VLM Parser                           │
│  • PDF/DOCX → Hybrid Parser (try rule → fallback VLM)        │
└────────────────────────────────────────────────────────────────┘
         ↓                      ↓                      ↓
┌─────────────────┐   ┌─────────────────┐   ┌────────────────┐
│  Rule-Based     │   │  VLM Parser     │   │  Hybrid Parser │
│  Parser         │   │  (Qwen2-VL)     │   │  (Combined)    │
│                 │   │                 │   │                │
│ • TXT (WA, TG)  │   │ • Images        │   │ • PDF (text)   │
│ • HTML (TG)     │   │ • Screenshots   │   │ • PDF (scan)   │
│ • JSON          │   │ • Scanned docs  │   │ • DOCX         │
│ • JSONL         │   │                 │   │                │
└─────────────────┘   └─────────────────┘   └────────────────┘
         │                      │                      │
         └──────────────────────┴──────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                   UNIFIED OUTPUT FORMAT                        │
│  Все parsers возвращают единый формат:                         │
│                                                                │
│  {                                                             │
│    "source": "path/to/file",                                   │
│    "type": "dialogue" | "knowledge",                           │
│    "messages": [                                               │
│      {                                                         │
│        "timestamp": "2024-11-16 14:30" | null,                │
│        "sender": "Иван",                                       │
│        "role": "user" | "assistant" | null,                   │
│        "content": "текст сообщения"                           │
│      }                                                         │
│    ],                                                          │
│    "knowledge": "текст документа" | [],                        │
│    "metadata": {                                               │
│      "parser_type": "rule_based" | "vlm" | "hybrid",          │
│      "format": "txt" | "html" | "json" | "png" | ...          │
│    }                                                           │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│              CLEANING & DEDUPLICATION                          │
│  • Normalize whitespace                                        │
│  • Replace URLs with [URL]                                     │
│  • Filter short messages (< 8 chars)                           │
│  • Filter stop-phrases ("ок", "ага", "+")                      │
│  • Deduplicate by content hash                                 │
│  • Role classification (user/assistant)                        │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│            DIALOGUE PAIR CONSTRUCTION                          │
│  • Group messages by conversation                              │
│  • Sort by timestamp                                           │
│  • Build prompt → completion pairs                             │
│  • Add conversation history (multi-turn support)               │
│                                                                │
│  Output: List[{                                                │
│    "prompt": "вопрос",                                         │
│    "completion": "ответ",                                      │
│    "history": [...previous messages...],                       │
│    "metadata": {...}                                           │
│  }]                                                            │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                TRAIN/VAL SPLIT                                 │
│  • Split 90/10 (train/validation)                              │
│  • Shuffle для randomization                                   │
│  • Stratify по длине если нужно                                │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│              FORMATTING FOR FINE-TUNING                        │
│  • Hugging Face format (messages with roles)                   │
│  • ShareGPT format (conversations)                             │
│  • Instruct format (instruction + response)                    │
│                                                                │
│  Formats:                                                      │
│  1. Hugging Face: {"messages": [{"role": ..., "content": ...}]}│
│  2. ShareGPT: {"conversations": [{"from": "human", "value": ...}]}│
│  3. Instruct: {"instruction": "...", "response": "..."}        │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                   OUTPUT FILES                                 │
│  • train.jsonl       - Training samples                        │
│  • eval.jsonl        - Validation samples                      │
│  • knowledge.jsonl   - Knowledge chunks (if any)               │
│  • manifest.json     - Metadata and stats                      │
└────────────────────────────────────────────────────────────────┘
```

***

## 🔧 Компоненты Pipeline (Детали)

### **1. Smart Router (`parsers/router.py`)**

**Задача:** Определяет какой parser использовать для каждого файла

**Логика:**
```
IF extension in [.txt, .log, .html, .htm, .json, .jsonl]:
    → Rule-Based Parser
    
ELSE IF extension in [.png, .jpg, .jpeg, .webp, .heic, .bmp]:
    → VLM Parser (Qwen2-VL OCR)
    
ELSE IF extension in [.pdf, .docx]:
    → Hybrid Parser (try rule-based → fallback VLM)
    
ELSE:
    → Skip (unsupported format)
```

**Опции:**
- `enable_vlm`: включить/выключить VLM parser
- `prefer_vlm`: использовать VLM даже для TXT (медленнее, но универсальнее)

***

### **2. Rule-Based Parser (`parsers/rule_based.py`)**

**Задача:** Парсинг структурированных форматов чатов

**Поддерживаемые форматы:**

| Формат | Источник | Метод парсинга |
|--------|----------|----------------|
| **TXT** | WhatsApp export | Regex паттерны: `[12.11.2024, 14:30] Иван: Привет` |
| **TXT** | Telegram text export | Regex паттерны: `12.11.2024, 14:30 Иван Привет` |
| **HTML** | Telegram HTML export | BeautifulSoup: `<div class="message">...</div>` |
| **JSON** | Structured dialogues | JSON parser: `{"messages": [...]}` |
| **JSONL** | Line-by-line | JSON per line |

**Ключевые функции:**
- `_parse_txt()` — TXT с regex паттернами (из вашего `chats.py`)
- `_parse_html()` — HTML через BeautifulSoup (из вашего `chats.py`)
- `_parse_json()` — JSON структурированные диалоги
- `_parse_jsonl()` — JSONL построчный парсинг
- `_normalize_message()` — нормализация к единому формату

**Что переносим из `chats.py`:**
- ✅ Все regex паттерны для TXT
- ✅ HTML парсинг через BeautifulSoup
- ✅ JSON/JSONL логику
- ✅ Multi-line message handling
- ✅ Encoding detection (UTF-8, cp1251)

***

### **3. VLM Parser (`parsers/vlm_parser.py`)**

**Задача:** OCR через Hugging Face `image-text-to-text` пайплайн на базе Qwen2-VL.

**Поддерживаемые форматы:**
- Images: PNG, JPG, JPEG, WEBP, HEIC, BMP
- Screenshots чатов (WhatsApp, Telegram, iMessage)
- Scanned documents (если PDF — image-based, тогда гибридный парсер конвертирует в изображение)

**Работа:**
1. Загружает изображение и конвертирует в RGB (Pillow).
2. Формирует multi-modal сообщение: изображение + prompt «Расшифруй весь текст ...».
3. Запускает HF pipeline `image-text-to-text` с моделью по умолчанию `prithivMLmods/Qwen2-VL-OCR-2B-Instruct`.
4. Возвращает plain text, далее передаёт его rule-based парсеру (для диалогов) или сохраняет в knowledge.

**Особенности:**
- Lazy loading пайплайна (загрузка Qwen2-VL при первом вызове).
- Требуется `huggingface-cli login`, чтобы скачать модель с Hugging Face.
- Работает на CPU/GPU через `transformers` + `torch`.

***

### **4. Hybrid Parser (`parsers/hybrid_parser.py`)**

**Задача:** Комбинированный подход для PDF/DOCX

**Логика:**
```
FOR each PDF/DOCX file:
    TRY:
        Extract text (pdfminer для PDF, python-docx для DOCX)
        IF text извлечен и length > 50:
            Parse через Rule-Based Parser (as TXT)
            RETURN result
    EXCEPT:
        Fallback to VLM Parser
        RETURN VLM result
```

**Преимущества:**
- Быстро для text-based PDF (rule-based)
- Работает для scanned PDF (VLM fallback)
- Оптимальный баланс speed/accuracy

***

### **5. Cleaning (`processing/cleaning.py`)**

**Задача:** Очистка и дедупликация сообщений

**Функции (из вашего `cleaning.py`):**
- `clean_and_deduplicate()` — основная функция
- `normalize_whitespace()` — нормализация пробелов
- `replace_urls()` — замена URL на `[URL]`
- `text_digest()` — SHA256 хеш для дедупликации
- `classify_role()` — определение user/assistant

**Фильтры:**
- Длина < 8 символов → remove
- Стоп-фразы ("ок", "ага", "+") → remove
- Дубликаты по content hash → remove
- Сообщения без sender → skip

***

### **6. Dialogue Builder (`processing/dialogue_builder.py`)**

**Задача:** Построение multi-trun пар

***

**Опции:**
- `--enable-vlm`: включить VLM parser (default: True)
- `--vlm-model`: VLM model ID (default: prithivMLmods/Qwen2-VL-OCR-2B-Instruct)
- `--prefer-vlm`: использовать VLM даже для TXT
- `--val-split`: процент validation данных (default: 0.1)
- `--format`: формат вывода (huggingface, sharegpt, instruct)
- `--validate`: валидация выходных данных
- `--log-level`: уровень логирования (DEBUG, INFO, WARNING, ERROR)

***

## 📊 Pipeline Workflow (Step-by-Step)

```
Step 1: INPUT
  └─ Сканирование input директорий/файлов

Step 2: ROUTING
  └─ Определение parser для каждого файла
  
Step 3: PARSING
  ├─ Rule-Based: TXT, HTML, JSON, JSONL
  ├─ VLM: Images, Screenshots
  └─ Hybrid: PDF, DOCX
  
Step 4: AGGREGATION
  └─ Сбор всех messages в единый список

Step 5: CLEANING
  ├─ Normalize whitespace
  ├─ Replace URLs
  ├─ Filter short/stop-phrases
  └─ Deduplicate by hash

Step 6: ROLE CLASSIFICATION
  └─ Определение user/assistant для каждого sender

Step 7: DIALOGUE PAIRS
  └─ Построение prompt → completion пар с историей

Step 8: TRAIN/VAL SPLIT
  └─ 90% train, 10% validation (shuffled)

Step 9: FORMATTING
  └─ Hugging Face / ShareGPT / Instruct format

Step 10: OUTPUT
  ├─ train.jsonl
  ├─ eval.jsonl
  ├─ knowledge.jsonl (if any)
  └─ manifest.json (stats)
```

***

## 🔄 Миграция из Старого Кода

### **Что переносим:**

| Старый файл | Новый файл | Действие |
|-------------|------------|----------|
| `chats.py` | `parsers/rule_based.py` | Миграция логики TXT/HTML/JSON/JSONL |
| `cleaning.py` | `processing/cleaning.py` | Сохранить без изменений |
| `utils.py` | `core/utils.py` | Сохранить без изменений |
| `schemas.py` | `core/schemas.py` | Сохранить без изменений |
| `validators.py` | `core/validators.py` | Сохранить без изменений |

### **Что удаляем:**

| Старый файл | Причина |
|-------------|---------|
| `annotations.py` | Эмоции/топики не нужны для fine-tuning |
| `preferences.py` | Стилистический анализ не нужен |
| `augment.py` | LLM-аугментация не нужна |
| `knowledge.py` | Функционал переносится в parsers |

### **Что создаем:**

| Новый файл | Задача |
|------------|--------|
| `parsers/router.py` | Smart routing логика |
| `parsers/vlm_parser.py` | Qwen2-VL OCR wrapper |
| `parsers/hybrid_parser.py` | Rule-based + VLM combo |
| `processing/dialogue_builder.py` | Построение пар |
| `processing/formatting.py` | Форматирование для training |

---

## 📦 Dependencies (requirements.txt)

```txt
# Core
python>=3.8

# Parsing
beautifulsoup4>=4.12.0      # HTML парсинг (Telegram)
pdfminer.six>=20221105       # PDF text extraction
python-docx>=1.1.0           # DOCX парсинг

# VLM (optional)
transformers>=4.40.0         # Qwen2-VL OCR
torch>=2.0.0                 # PyTorch
pillow>=10.0.0               # Image processing
pdf2image>=1.17.0            # PDF → Image conversion

# Utils
tqdm>=4.66.0                 # Progress bars
```

***

## 🎯 Ключевые Преимущества Новой Архитектуры

### **1. Простота**
- 6 файлов вместо 10 (~25KB кода вместо 55KB)
- Чистая архитектура, легко читать и поддерживать
- Нет лишней логики (аннотации, стилистика, DPO)

### **2. Гибкость**
- Поддержка любых форматов через VLM
- Rule-based для известных форматов (быстро)
- Hybrid approach для best of both worlds
- Легко добавить новый parser

### **3. Эффективность**
- Оптимальный баланс speed/quality
- Lazy loading VLM (загружается только если нужен)
- Caching возможен (по file hash)
- Параллелизация парсинга (будущее улучшение)

### **4. Универсальность**
- TXT: WhatsApp, Telegram text
- HTML: Telegram HTML export
- JSON/JSONL: structured data
- Images: screenshots любых мессенджеров
- PDF/DOCX: документы (text + scanned)

### **5. Production-Ready**
- Валидация выходных данных
- Error handling с fallbacks
- Логирование всех операций
- Manifest с метаданными
- Easy integration в no-code платформу

***

## 🚀 Roadmap Реализации

### **Phase 1: Core Infrastructure**
- [ ] Создать структуру папок
- [ ] Перенести `schemas.py`, `utils.py`, `validators.py`
- [ ] Реализовать `router.py` (smart routing)
- [ ] Unit tests для router

### **Phase 2: Rule-Based Parser**
- [ ] Мигрировать логику из `chats.py` → `rule_based.py`
- [ ] Сохранить TXT парсинг (WhatsApp, Telegram)
- [ ] Сохранить HTML парсинг (BeautifulSoup)
- [ ] Сохранить JSON/JSONL парсинг
- [ ] Unit tests для всех форматов

### **Phase 3: VLM Parser **
- [ ] Реализовать `vlm_parser.py`
- [ ] Интеграция Qwen2-VL OCR
- [ ] Тестирование на screenshots
- [ ] Prompt engineering для лучшего качества

### **Phase 4: **
- [ ] Перенести `cleaning.py` (без изменений)
- [ ] Реализовать `dialogue_builder.py`
- [ ] Реализовать `formatting.py` (3 формата)
- [ ] Unit tests

### **Phase 5:**
- [ ] Упрощенный CLI
- [ ] End-to-end integration tests
- [ ] Benchmark на реальных данных
- [ ] Documentation

### **Phase 6:**
- [ ] Performance optimization
- [ ] Error handling improvements
- [ ] Logging enhancements
- [ ] Deploy в no-code платформу

*

---

## ✅ Выводы

**Новая архитектура:**
- ✅ **Проще:** 6 модулей вместо 10
- ✅ **Гибче:** поддержка любых форматов
- ✅ **Эффективнее:** оптимальный баланс
- ✅ **Чище:** никакого лишнего кода
- ✅ **Ready:** для no-code платформы

**Убрано:**
- ❌ Аннотации (не нужны)
- ❌ Стилистика (не нужна)
- ❌ Аугментация (не нужна)
- ❌ DPO (не нужно)

**Сохранено:**
- ✅ Вся логика парсинга TXT/HTML/JSON
- ✅ Cleaning & deduplication
- ✅ Utilities & validation
- ✅ Schemas

**Добавлено:**
- 🆕 VLM parser (Qwen2-VL OCR)
- 🆕 Smart router
- 🆕 Hybrid parser
- 🆕 Dialogue builder
- 🆕 Multiple output formats
