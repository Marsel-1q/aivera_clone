# AIVERA - Personal AI Doubles Platform

A modern web application for creating, training, and testing personal AI clones. Built with Next.js 15, React 19, and Tailwind CSS, featuring a high-end "cyberpunk/neon" aesthetic, plus minimal backend endpoints that wrap the existing Python tooling (`dataset_pipeline/cli.py`, `train_qlora.py`) for no-code fine-tuning and LoRA inference.

## 🚀 Tech Stack

- **Framework**: [Next.js 15](https://nextjs.org/) (App Router)
- **Language**: TypeScript
- **Styling**: [Tailwind CSS](https://tailwindcss.com/) (v4)
- **UI Components**: [Shadcn UI](https://ui.shadcn.com/)
- **Icons**: [Lucide React](https://lucide.dev/)
- **Animation**: CSS Animations, Tailwind Animate

## 📂 Project Structure

The project follows the standard Next.js App Router structure with route groups for organization:

```
src/
├── app/
│   ├── (auth)/                 # Authentication Routes
│   │   ├── login/              # Login Page
│   │   └── signup/             # Signup Page
│   ├── (dashboard)/            # Protected Dashboard Routes
│   │   ├── dashboard/          # Main Overview
│   │   ├── clones/             # Clones Management
│   │   │   ├── [cloneId]/      # Individual Clone Workspace (Tabs: Overview, Data, Behavior, Tests, Integrate)
│   │   │   ├── new/            # Create Clone Wizard (Multi-step)
│   │   │   └── page.tsx        # Clones List
│   │   ├── projects/           # Projects Management
│   │   ├── datasets/           # Dataset Management
│   │   ├── training/           # Training Status
│   │   ├── tests/              # Global Testing
│   │   ├── deploy/             # Deployment Options
│   │   └── settings/           # User Settings
│   ├── globals.css             # Global Styles & Tailwind Config
│   ├── layout.tsx              # Root Layout
│   └── page.tsx                # Landing Page
├── components/
│   ├── ui/                     # Reusable UI Components (Shadcn)
│   └── layout/                 # Layout Components (Sidebar, Header)
├── lib/                        # Utilities (cloneStore, jobStore, etc.)
├── uploads/                    # Runtime uploads (datasets/jobs) — created on server
└── scripts/                    # Python helper for LoRA chat (chat_with_lora.py)
```

## ✨ Key Features Implemented

### 1. Landing Page (`/`)
- **Visuals**: Full-screen "Starry Void" background with a borderless, floating "Digital Brain" visual.
- **Effects**: "Cold Flame" aura, seamless blending using CSS `mix-blend-mode` and gradients.
- **Content**: Hero section, Features grid, Pricing plans.

### 2. Authentication (`/login`, `/signup`)
- **Design**: Glassmorphism cards with neon accents.
- **Flow**: Redirects to `/dashboard` upon successful interaction.

### 3. Dashboard (`/dashboard`)
- **Layout**: Persistent Sidebar navigation with active state highlighting.
- **Overview**: Displays key metrics (Active Clones, Total Conversations, etc.).

### 4. Clone Management (`/clones`)
- **List View**: Displays all user clones (from backend), with status (`training/ready/failed`), dataset count, timestamps.
- **Create Workflow (`/clones/new`)**: A 4-step wizard:
    1.  **Model Selection**: Choose base model (e.g., Qwen 2.5 VL).
    2.  **Dataset Upload**: Drag & drop interface for files (stored in `uploads/datasets/<uuid>`).
    3.  **System Prompt & Persona**: Define persona id and system prompt (passed to training).
    4.  **Training**: Launch the fine-tuning process (creates job + clone record).

### 5. Clone Workspace (`/clones/[cloneId]`)
- **Tabs Navigation**:
    - **Overview**: Stats and recent activity.
    - **Data**: Manage knowledge base.
    - **Behavior**: Configure system prompts and personality sliders.
    - **Tests**: Interactive chat interface for testing.
    - **Integrate**: Messaging integrations (Telegram active; WhatsApp/Google/Slack placeholders). Start/stop clone worker.

### 6. Training Backend (Minimal)
- **/api/datasets** — upload dataset (form-data), save to `uploads/datasets/<uuid>`.
- **/api/training** — run `dataset_pipeline/cli.py` then `train_qlora.py`. Accepts `modelId`, `datasetId`, `systemPrompt`, `persona`, `cloneName`. Returns `jobId` + `cloneId`. Needs `ENABLE_REAL_TRAINING=true` to launch real Python processes; otherwise simulates.
- **/api/training/[id]** — job status/logs (in-memory).
- **/api/clones** — list clones (in-memory, tied to jobs).
- **/api/tests/chat** — chat with trained clone using base model + LoRA via Python helper (`scripts/chat_with_lora.py`).
- State is in-memory; outputs (LoRA adapter) stored under `uploads/jobs/<jobId>/outputs/lora_adapter`.

### 7. Knowledge (RAG) Management
- CLI уже режет знания в `knowledge.jsonl` и строит RAG-индекс через `rag/index_builder.py` (автоматически при реальном training).
- Вкладка **Data** показывает только знания (RAG), имена файлов + размер. Есть кнопка **Rebuild Knowledge** — переупаковка датасета и пересборка индекса без переобучения модели.
- Удаление знания (корзина) удаляет файл, чистит `knowledge.jsonl` и пересобирает/очищает индекс.

### 8. Clone Worker & Messaging (Integrate)
- Новая вкладка **Integrate** вместо Deploy. Список платформ: Telegram (рабочая), WhatsApp/Google/Slack — заглушки.
- API/хранилище интеграций: `uploads/integrations.json` через `integrationStore`. Настраивает токен/active.
- **Clone worker**: `/api/clones/[cloneId]/start` запускает отдельный процесс `scripts/clone_worker.js`, передаёт cloneId/model/adapterDir/ragIndex/integrations; `/api/clones/[cloneId]/start` c action=stop — гасит.
- Telegram бот в воркере (telegraf): слушает сообщения, дергает `/api/tests/chat` с нужным cloneId, отправляет ответ.
- Heartbeat воркера — через IPC; `workerManager` обновляет `isRunning`.

### 9. Tests (`/tests`)
- Select a clone and chat; backend calls `/api/tests/chat`, which loads base model + adapter and generates a reply. If clone not ready/adapter missing — error.

## 🛠️ Getting Started

1.  **Install Node deps** (при наличии сети):
    ```bash
    npm install
    ```

2.  **Python env** (тот же, что использует Next для запуска CLI):
    ```bash
    cd /path/to/startup
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install torch torchvision transformers peft datasets bitsandbytes trl qwen-vl-utils tensorboard
    pip install -r dataset_pipeline/requirements.txt
    ```

3.  **Запуск Next с реальным обучением**:
    ```bash
    cd website_clone
    ENABLE_REAL_TRAINING=true npm run dev   # или build/start
    ```
    Без флага обучение симулируется.

4.  **Использование**:
    - `/clones/new`: загрузить датасет, задать persona/system prompt, стартовать обучение.
    - `/clones`: видеть статус клона (ready/training/failed).
    - `/tests`: выбрать клон, задать вопрос — ответ через обученный LoRA (Python helper).
    - `/clones/[id]/integrate`: ввести токен Telegram, включить интеграцию, запустить клон (Initialize) — воркер поднимет бота и будет отвечать через модель.

5.  **Node deps для Telegram воркера**:
    ```bash
    cd website_clone
    npm install  # добавлен telegraf
    ```

## 📝 Current Status

- **Frontend**: Landing, auth, dashboard, clones/tests, Integrate (управление интеграциями и запуском воркера).
- **Backend**: API для датасетов, обучения, статусов, клонов, тест-чата, интеграций, старта/остановки воркера; in-memory сторы + файловое хранилище интеграций.
- **Inference**: `/api/tests/chat` → `scripts/chat_with_lora.py` (GPU/CUDA для реального инференса). Воркер повторно использует этот endpoint.
- **RAG**: Автосборка индекса при обучении; ручное Rebuild/удаление знаний из Data.
- **Workers**: Отдельный процесс на клон; Telegram бот активен при наличии токена/активации. Для прод — вынести в сервис/очередь.
