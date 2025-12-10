* Клиент скачал → распаковал → запустил `run.sh` / `run.bat`.
* Поднялся `ai-clone-server`:

  * веб-админка на `http://localhost:3000`
  * локальный чат
  * возможность править системный промпт
  * включить/выключить Telegram-бота
  * добавить документы в RAG
* Все ответы модели считаются локально.

Ниже — **конкретная архитектура и план реализации**.

---

## 1. Цель MVP

Сейчас **НЕ делаем**:

* платформу с обучение / дообучение LoRA; Клон уже готов в outputs/promt_optimization/iteration_01/lora_adapter , его возьмём для тестов
* облачную панель, биллинг, мульти-клоновость и т.д.

Сейчас у нас реализована загрузка датасета, подготовка датасета и запуск обучения. Теперь же нужно быстро протестировать локальный запуск модели на стороне клиента с бандлом который клиент получает после тренировки модели. Ниже всё подробно расписано. МЫ НЕ ТРОГАЕМ ЧАСТЬ С ТРЕНИРОВКОЙ МОДЕЛИ, а работаем над корректным бандлом который при запуске - запускает работу модели, запускается веб панель на локалхост через который можно настраивать системный промт для модели , подключать / отключать мессенджеры.

Сейчас **ДЕЛАЕМ**:

* один клон (одна модель + один системный промпт);
* один бандл, который:

  * запускает локальный сервер,
  * даёт веб-админку,
  * умеет подключить/отключить Telegram-бота,
  * умеет принимать локальные документы для RAG,
  * использует модель локально (CPU/GPU, зависит от твоего выбора).

---

## 2. Архитектура на уровне компонент

Предлагаю такую картину:

```text
+---------------------+
|   Web Admin (UI)    |  <-- React/Vue/HTML, работает в браузере
+----------+----------+
           |
           v  HTTP (localhost:3000)
+----------+-----------------------------+
|           ai-clone-server              |
|  (backend + LLM + RAG + connectors)    |
+----------------+----------------------+
|  ConfigManager |  ModelEngine         |
|  RAGEngine     |  ConnectorManager    |
+----------------+----------------------+
           |
           v
     Файлы бандла (models, data, config)
```

### Основные модули внутри `ai-clone-server`:

1. **ConfigManager**

   * читает/пишет `config/config.yaml`
   * отдаёт настройки другим модулям.

2. **ModelEngine**

   * грузит base-модель (из `./models/base`)
   * опционально грузит LoRA (из `./models/lora`)
   * метод типа `generate(system_prompt, history, rag_context, user_message) -> answer`.

3. **RAGEngine**

   * хранит документы (например, в `./data/rag`)
   * умеет:

     * добавить документ,
     * пересчитать эмбеддинги,
     * сделать `search(query) -> топ_k кусочков текста`.

4. **ConnectorManager**

   * стартует/останавливает коннекторы по конфигу.
   * для MVP — только `TelegramConnector`.

5. **TelegramConnector**

   * читает `bot_token` из конфига,
   * делает long-poll `getUpdates`,
   * на каждое сообщение:

     * отправляет текст в `ModelEngine` (через общий оркестратор),
     * получает ответ,
     * отправляет `sendMessage`.

6. **HTTP API (админка)**

   * REST/JSON эндпоинты:

     * `/api/clone` — получить/обновить системный промпт;
     * `/api/messengers/telegram` — включить/выключить, задать токен;
     * `/api/rag/documents` — загрузить документ, список документов;
     * `/api/chat/test` — локальный чат прямо в админке.

---

## 3. Структура бандла (папки/файлы)

Пример:

```text
ai-clone-bundle/
  run.sh
  run.bat
  README.md

  ai_clone_server/          # сам код (Python/Go/Node - как решишь)
    app.py
    connectors/
      telegram_connector.py
    core/
      config_manager.py
      model_engine.py
      rag_engine.py
      orchestrator.py
    webui/                  # статика админки (build React/Vue)
      index.html
      assets/...

  models/
    base/
      model.bin / model.gguf / модель HF
    lora/
      clone_lora.safetensors   # пока можно даже не использовать, но структура уже есть

  config/
    config.yaml

  data/
    rag/                      # векторная БД (SQLite/Chroma/и т.п.)
    logs/
```

`run.sh` / `run.bat` внутри просто запускают `python ai_clone_server/app.py` или бинарь.

---

## 4. Пример `config.yaml` для MVP

```yaml
clone:
  id: "local_clone_1"
  name: "My Local AI Clone"
  system_prompt: |
    Ты персональный ассистент. Отвечай дружелюбно, по делу и на русском.

model:
  backend: "llama_cpp"             # или "transformers"
  base_model_path: "./models/base/model.gguf"
  lora_path: "./models/lora/clone_lora.safetensors"  # для MVP можно игнорировать
  max_tokens: 512
  temperature: 0.7

rag:
  enabled: true
  db_path: "./data/rag"
  top_k: 5

admin_panel:
  host: "127.0.0.1"
  port: 3000

messengers:
  telegram:
    enabled: false
    bots:
      - bot_id: "default"
        token: ""                # клиент заполнит в UI
        linked_clone_id: "local_clone_1"
```

---

## 5. Поведение при старте бандла

Когда клиент запускает `run.sh`:

1. **ai-clone-server стартует:**

   * читает `config.yaml`;
   * инициализирует `ModelEngine`:

     * проверяет наличие модели;
     * загружает базовую модель;
     * (опционально) применяет LoRA;
   * инициализирует `RAGEngine`:

     * создаёт/открывает локальную БД.
   * инициализирует `ConnectorManager`:

     * если `telegram.enabled == true` и у ботов есть токен → запускает `TelegramConnector`.
   * поднимает HTTP-сервер (FastAPI/Flask/Express/etc.) на `http://127.0.0.1:3000`.

2. **Web UI (админка):**

   * отдаётся по `GET /` — статика `webui/index.html`.
   * фронт ходит к API типа `/api/...`.

---

## 6. HTTP API (черновая спецификация для MVP)

### 6.1. Клон и системный промпт

* `GET /api/clone`

  * ответ:

    ```json
    {
      "id": "local_clone_1",
      "name": "My Local AI Clone",
      "system_prompt": "..."
    }
    ```

* `PUT /api/clone`

  * тело:

    ```json
    {
      "system_prompt": "Новый текст промпта..."
    }
    ```
  * сервер:

    * обновляет `config.yaml`,
    * держит новый промпт в памяти.

### 6.2. Мессенджеры → Telegram

* `GET /api/messengers/telegram`

  * возвращает текущий конфиг:

    ```json
    {
      "enabled": true,
      "bots": [
        {
          "bot_id": "default",
          "token": "123:ABC",
          "linked_clone_id": "local_clone_1"
        }
      ]
    }
    ```

* `PUT /api/messengers/telegram`

  * тело:

    ```json
    {
      "enabled": true,
      "bots": [
        {
          "bot_id": "default",
          "token": "123:ABC",
          "linked_clone_id": "local_clone_1"
        }
      ]
    }
    ```
  * сервер:

    * обновляет `config.yaml`,
    * перезапускает/стартует/останавливает `TelegramConnector`.

### 6.3. RAG

* `GET /api/rag/documents`

  * список документов (id, имя, размер, дата).

* `POST /api/rag/documents`

  * multipart/form-data: `file = <документ>`
  * сервер:

    * сохраняет файл в `./data/rag/files/` (если нужно),
    * режет на чанки,
    * считает эмбеддинги,
    * кладёт в векторную БД.

### 6.4. Локальный чат (для теста)

* `POST /api/chat/test`

  * тело:

    ```json
    {
      "message": "Привет, кто ты?"
    }
    ```
  * сервер:

    * берёт системный промпт из конфига,
    * достаёт контекст из RAG,
    * вызывает `ModelEngine.generate(...)`,
    * возвращает:

      ```json
      {
        "answer": "Привет, я локальный ИИ-клон!"
      }
      ```

---

## 7. Технологический стек (рекомендация для быстрого MVP)

### Backend (`ai-clone-server`)

Вариант для тебя (Python):

* **API / веб-сервер**: `FastAPI` + `uvicorn`.
* **LLM**:

  * Для простого старта: `llama-cpp-python` + локальная GGUF-модель (LLaMA-3 8B Q4_K_M, например).
  * LoRA сейчас можно не подключать — достаточно `system_prompt` + RAG, но архитектуру оставляем готовой для LoRA.
* **RAG**:

  * `sentence-transformers` (локальная embedding-модель) + `faiss` или `chromadb`.
* **Конфиг**: `PyYAML` для `config.yaml`.

### Web UI

* Простой **React/Vite** или даже `HTML + vanilla JS` для MVP:

  * Страница с вкладками:

    * “Клон” — текстовое поле системного промпта.
    * “Мессенджеры” — формы для Telegram.
    * “Знания (RAG)” — загрузка документов + список.
    * “Тестовый чат” — textarea + блок ответа.

---

## 8. Пошаговый план реализации (итерации)

### Итерация 1: самый минимальный скелет

1. Создать структуру бандла (папки, `config.yaml`).
2. Написать `app.py`, который:

   * читает конфиг,
   * поднимает FastAPI на `/`,
   * отдаёт статический HTML с “Hello, Admin”.
3. Добавить эндпоинт `/api/clone` (GET/PUT) и хранить `system_prompt` в `config.yaml`.

Проверка:
Запуск `run.sh` → открываешь `localhost:3000` → можешь увидеть и изменить системный промпт.

---

### Итерация 2: подключить модель и локальный чат

1. Подключить `llama-cpp-python` (или другой простой бэкенд).
2. Реализовать `ModelEngine.generate(...)`.
3. Добавить endpoint `/api/chat/test`.

Проверка:
В админке на вкладке “Чат” пишешь текст → получаешь ответ от локальной модели.

---

### Итерация 3: RAG

1. Добавить `RAGEngine`:

   * файлы в `./data/rag/files/`;
   * база эмбеддингов в `./data/rag/vector_db`.
2. Добавить эндпоинты `/api/rag/documents` GET/POST.
3. В `generate` перед вызовом модели:

   * делать поиск по RAG,
   * подмешивать топ-k фрагментов в промпт.

Проверка:
Загрузил документ → задаёшь вопрос в чате → видишь, что модель использует контент документа.

---

### Итерация 4: TelegramConnector

1. Написать `TelegramConnector`:

   * отдельный поток/таск, который:

     * читает токен из `config.yaml`,
     * если `enabled: true`, стартует long-poll `getUpdates`,
     * на новые сообщения вызывает `ModelEngine.generate(...)`,
     * отвечает `sendMessage`.
2. Реализовать `/api/messengers/telegram`:

   * менять конфиг;
   * запускать/останавливать коннектор через `ConnectorManager`.

Проверка:
Создаёшь бота у @BotFather → токен вставляешь в админке → включаешь Telegram → бот начинает отвечать локально.

---

### Итерация 5: “полировка бандла”

1. Сделать `run.sh` / `run.bat` (внутри: активация venv, запуск `uvicorn app:app`).
2. Написать `README.md`:

   * как распаковать,
   * как запустить,
   * как открыть админку,
   * как создать Telegram-бота и вставить токен.
3. Проверить всё на “чистой” машине (как будто ты клиент).

---

