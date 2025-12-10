# Supabase Backend Implementation Plan for AI Clone Platform

Этот документ описывает, как перевести текущую платформу цифровых клонов на полноценный бэкенд с Supabase: много‑пользовательская архитектура, авторизация, привязка клонов к пользователям, хранение метаданных в Postgres и использование RLS.

## 1. Цели

- Каждый пользователь имеет свой аккаунт (Supabase Auth).
- Все сущности платформы привязаны к `user_id`:
  - клоны,
  - джобы обучения,
  - датасеты,
  - интеграции (например, Telegram).
- Файлы (LoRA адаптеры, датасеты, RAG‑индексы) продолжают жить в `uploads/` и Python‑пайплайне.
- Supabase хранит **метаданные** и обеспечивает:
  - разграничение доступа (Row Level Security),
  - нормальные запросы (фильтрация, сортировка),
  - работу в multi‑tenant режиме (много пользователей).

---

## 2. Архитектура с Supabase

### 2.1. Компоненты

- **Supabase**
  - **Auth** — email+password (и позже OAuth, если нужно).
  - **Postgres** — таблицы: `profiles`, `clones`, `training_jobs`, `datasets`, `integrations`.
  - **RLS** — политики на уровне строк: каждый пользователь видит только свои записи.
  - (опционально позже) Storage для файлов.

- **Next.js 15 (App Router)**
  - `@supabase/supabase-js` + `@supabase/ssr` для работы с Auth и БД.
  - Cookie‑based сессии: Supabase прокидывает JWT пользователя в запросы → RLS работает автоматически.
  - Все роуты в `(dashboard)` защищены: только авторизованный пользователь.

- **Python‑часть (уже есть)**
  - `dataset_pipeline`, `train_qlora.py`, `rag/index_builder.py`, `chat_with_lora.py`.
  - Supabase используется как «реестр»:
    - где лежит датасет,
    - где лежит LoRA адаптер,
    - какой статус у джоба,
    - какой клон связан с этим джобом.

### 2.2. Связка сущностей

- `auth.users` — системная таблица Supabase, где живут учетные записи.
- `profiles` — расширение `auth.users` (доп. поля).
- `clones.user_id` → владелец клона.
- `training_jobs.user_id` → кто запустил обучение.
- `datasets.user_id` → чей датасет.
- `integrations.user_id` → чей набор интеграций.

RLS гарантирует, что пользователь не может получить доступ к чужим строкам в этих таблицах.

---

## 3. Схема БД (Postgres / Supabase)

Ниже логическая схема таблиц; реальный SQL можно будет собрать по этим описаниям.

### 3.1. Таблица `profiles`

- Поля:
  - `id uuid primary key references auth.users (id)`
  - `email text`
  - `full_name text`
  - `created_at timestamptz default now()`
- Назначение:
  - 1:1 к `auth.users`, хранит пользовательский профиль.
  - Email дублируется для удобства.
- RLS:
  - `select/update`: `auth.uid() = id`
  - New profile создается триггером после регистрации пользователя.

### 3.2. Таблица `clones`

- Поля:
  - `id uuid primary key default gen_random_uuid()`
  - `user_id uuid references auth.users(id)` — владелец.
  - `name text` — название клона.
  - `model_id text` — ID базовой модели (например, `Qwen/Qwen2.5-VL-7B-Instruct`).
  - `status text` — `training | ready | failed`.
  - `dataset_id uuid` — UUID датасета (совпадает с именем папки `uploads/datasets/<dataset_id>`).
  - `dataset_count integer` — количество файлов в датасете.
  - `job_id uuid` — ссылка на `training_jobs.id`.
  - `api_key text` — уникальный токен для внешнего доступа (генерируется при создании).
  - `knowledge_file text` — полный путь до `knowledge.jsonl`.
  - `rag_index_dir text` — путь до директории индекса RAG.
  - `created_at timestamptz default now()`
  - `updated_at timestamptz default now()`
- RLS:
  - `select/update/delete`: `user_id = auth.uid()`
  - `insert`: либо задаём `user_id` триггером из `auth.uid()`, либо проверяем в policy.

### 3.3. Таблица `training_jobs`

- Поля:
  - `id uuid primary key default gen_random_uuid()`
  - `user_id uuid references auth.users(id)`
  - `clone_id uuid references clones(id)`
  - `model_id text`
  - `dataset_id uuid`
  - `system_prompt text`
  - `persona text`
  - `adapter_dir text` — путь к LoRA адаптеру.
  - `processed_dir text` — путь к `processed_dataset`.
  - `knowledge_file text`
  - `rag_index_dir text`
  - `knowledge_count integer`
  - `status text` — `queued | running | succeeded | failed`
  - `logs text[]` или отдельная таблица `job_logs`.
  - `error text`
  - `created_at timestamptz default now()`
  - `updated_at timestamptz default now()`
- RLS:
  - `select/update`: `user_id = auth.uid()`
  - `insert`: `user_id = auth.uid()`

### 3.4. Таблица `datasets`

- Поля:
  - `id uuid primary key` — совпадает с именем папки `uploads/datasets/<id>`.
  - `user_id uuid references auth.users(id)`
  - `clone_id uuid references clones(id) null` — может быть привязан к клону (или общий).
  - `file_count integer`
  - `created_at timestamptz default now()`
  - `updated_at timestamptz default now()`
- RLS:
  - `select/update/delete`: `user_id = auth.uid()`

### 3.5. Таблица `integrations`

- Поля:
  - `id uuid primary key default gen_random_uuid()`
  - `user_id uuid references auth.users(id)`
  - `clone_id uuid references clones(id)`
  - `platform text` — `'telegram' | 'whatsapp' | 'google' | 'slack'`
  - `active boolean`
  - `token text` — токен бота/интеграции.
  - `updated_at timestamptz default now()`
- RLS:
  - `select/update/delete`: `user_id = auth.uid()`
  - `insert`: `user_id = auth.uid()`

### 3.6. Демо‑клон

Варианты:

- Либо отдельная запись в `clones` с `user_id = null` и специальной policy (read‑only для всех).
- Либо просто удалить демо и работать только с реальными пользователями.

---

## 4. Интеграция Supabase в Next.js 15 (App Router)

### 4.1. Подготовка проекта Supabase

1. Создать проект на [supabase.com](https://supabase.com/).
2. В интерфейсе Supabase:
   - раздел **Settings → API**:
     - `Project URL` → `SUPABASE_URL`.
     - `anon public` → `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
     - `service_role` → `SUPABASE_SERVICE_ROLE_KEY` (см. ниже).
3. Создать таблицы `profiles`, `clones`, `training_jobs`, `datasets`, `integrations` и включить RLS.

> `SUPABASE_SERVICE_ROLE_KEY` — секретный ключ с ролью `service_role`, который может обходить RLS. Используется **только на сервере** (Next.js API routes, воркеры, cron), никогда на клиенте.

### 4.2. Настройки в `website_clone`

1. Добавить зависимости:

```bash
npm install @supabase/supabase-js @supabase/ssr
```

2. Добавить `.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

### 4.3. Клиенты Supabase

Создать вспомогательные модули:

- `src/lib/supabaseClient.ts` — браузерный клиент:
  - `createBrowserClient(NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY)`.
- `src/lib/supabaseServer.ts` — серверный клиент:
  - `createServerClient` из `@supabase/ssr`, который работает с cookies (App Router).

Использование:

- `(auth)` страницы (`/login`, `/signup`) — client‑side Supabase auth.
- `(dashboard)` layout и страницы — серверный клиент для проверки сессии и запросов к БД.
- `src/app/api/...` — серверный клиент внутри route handlers.

### 4.4. Auth‑страницы (login/signup)

Переписать текущие заглушки на реальную авторизацию:

- `/signup`:
  - форма email + пароль,
  - вызов `supabase.auth.signUp({ email, password })`,
  - обработка ошибок (email занят, слабый пароль и т.д.),
  - редирект на `/dashboard` после успешной регистрации/подтверждения (в зависимости от настроек Supabase).

- `/login`:
  - форма email + пароль,
  - `supabase.auth.signInWithPassword({ email, password })`,
  - редирект на `/dashboard`.

### 4.5. Защита маршрутов (App Router)

В `(dashboard)/layout.tsx`:

- На серверной стороне:
  - создать серверный Supabase‑клиент,
  - вызвать `supabase.auth.getUser()`.
- Если `user` отсутствует — `redirect("/login")`.

В API маршрутах:

- В начале каждого handler’а:
  - создать серверный Supabase‑клиент,
  - `const { data: { user } } = await supabase.auth.getUser();`
  - если `!user` → вернуть `401 Unauthorized`.

Так мы защищаем и UI, и сами API, даже если UI кто‑то попытается обойти.

---

## 5. Привязка клонов, джобов и датасетов к пользователю

Главная идея: **локальные `cloneStore.ts` и `jobStore.ts` заменить на Supabase**, а файлы в `uploads/` оставить как есть.

### 5.1. Замена `cloneStore` / `jobStore`

Сейчас:

- `cloneStore.ts` хранит клонов в `uploads/data/clones.json`.
- `jobStore.ts` хранит джобы в `uploads/data/jobs.json`.

Будет:

- Функции `createClone`, `updateClone`, `listClones`, `getClone` реализованы через Supabase:
  - `insert`/`update`/`select` из таблицы `clones`.
  - `user_id` устанавливается из `auth.uid()` (через серверный Supabase‑клиент).
- Функции `createJob`, `updateJob`, `getJob`, `listJobs` — через таблицу `training_jobs`.

Для воркера/тяжёлых задач:

- отдельные функции, использующие `SUPABASE_SERVICE_ROLE_KEY`, чтобы читать/обновлять джобы и клонов без привязки к текущему пользователю (системные операции).

### 5.2. Обновление `/api/training`

Сейчас `POST /api/training`:

- создаёт job через `createJob` (локальный стор),
- создаёт клон через `createClone`,
- запускает Python‑пайплайн.

После интеграции:

1. В handler’е:
   - получить текущего пользователя через Supabase (`auth.getUser()`).
   - убедиться, что он авторизован.
2. Создать запись в `datasets` (если `datasetId` новый):
   - `id = datasetId`,
   - `user_id = user.id`,
   - `file_count` из файловой системы.
3. Создать запись в `training_jobs`:
   - `user_id = user.id`,
   - `model_id`, `dataset_id`, `system_prompt`, `persona` и т.д.
4. Создать запись в `clones`:
   - `user_id = user.id`,
   - `job_id = job.id`,
   - `dataset_id`, `dataset_count`,
   - сгенерировать `api_key`,
   - `status = 'training'`.
5. Вернуть клиенту `{ jobId, cloneId, status: 'queued' }`.
6. Логику запуска Python (spawn, обновление статусов) оставить, но внутри использовать `training_jobs`/`clones` в Supabase вместо локальных стор.

### 5.3. Обновление `/api/clones` и `/api/clones/[cloneId]`

- `GET /api/clones`:
  - `select * from clones where user_id = auth.uid() order by created_at desc`.
- `GET /api/clones/[cloneId]`:
  - `select * from clones where id = :clone_id and user_id = auth.uid()`.
  - если не найдено → `404`.
- `PATCH /api/clones/[cloneId]`:
  - обновление только своей строки (`user_id = auth.uid()`).

UI (`/clones`, `/clones/[cloneId]`) автоматически начинает работать в multi‑tenant режиме: запросы к API возвращают только клонов текущего пользователя.

### 5.4. Datasets + Knowledge (RAG)

- При загрузке файлов через `/api/datasets`:
  - использовать `auth.getUser()` в handler’е,
  - сохранять файлы в `uploads/datasets/<datasetId>` как сейчас,
  - обновлять таблицу `datasets`:
    - `file_count`,
    - `user_id = user.id`.

- При пересборке знаний `/api/clones/[cloneId]/knowledge`:
  - читать клон из Supabase,
  - запускать `dataset_pipeline` и `rag/index_builder.py` как сейчас,
  - обновлять в Supabase:
    - `clones.knowledge_file`,
    - `clones.rag_index_dir`,
    - `clones.knowledge_count`,
    - при необходимости — `training_jobs.*` для связанного джоба.

### 5.5. Интеграции и воркер

#### Интеграции

Вместо `integrationStore.ts` (JSON в `uploads/integrations.json`):

- `getIntegrations(cloneId)`:
  - `select * from integrations where clone_id = :cloneId and user_id = auth.uid()`.
- `upsertIntegration`:
  - `insert`/`update` в таблицу `integrations` с `user_id = auth.uid()`.

UI вкладки Integrate (`/clones/[cloneId]/integrate`) работает через эти API и автоматически ограничивается текущим пользователем.

#### Воркер (`clone_worker.js` / `workerManager.ts`)

- `workerManager.startCloneWorker(cloneId)`:
  - использовать сервисный Supabase‑клиент (с `SUPABASE_SERVICE_ROLE_KEY`),
  - прочитать:
    - клон по `id`,
    - связанный джоб по `job_id`,
    - интеграции по `clone_id`.
  - сформировать `env` для воркера:
    - `MODEL_ID`, `ADAPTER_DIR`, `RAG_INDEX_DIR`, `INTEGRATIONS`, `SYSTEM_PROMPT` и т.д.
- Воркер общается с API (`/api/tests/chat`) как сейчас; всё уже связано с `cloneId`, а сам клон и индекс привязаны к пользователю в Supabase.

---

## 6. Этапы внедрения (roadmap)

### Этап 0 — Supabase проект + схема

1. Создать проект Supabase.
2. Настроить Auth (email+password).
3. Создать таблицы `profiles`, `clones`, `training_jobs`, `datasets`, `integrations`.
4. Включить RLS и добавить политики:
   - во всех таблицах доступ к строкам только при `user_id = auth.uid()` (или `id = auth.uid()` для `profiles`).

### Этап 1 — Базовая интеграция Auth

1. Подключить `@supabase/supabase-js` и `@supabase/ssr`.
2. Реализовать `supabaseClient` (browser) и `supabaseServer` (server).
3. Переписать `/login` и `/signup` на реальный `supabase.auth.signUp/signInWithPassword`.
4. Защитить `(dashboard)/layout.tsx`:
   - редирект на `/login`, если `auth.getUser()` вернул `null`.

### Этап 2 — Привязка клонов к пользователю (read‑only)

1. Написать слой доступа `cloneRepository`/`jobRepository` поверх Supabase.
2. В `/clones` и `/clones/[cloneId]` перейти на чтение клонов/джобов из Supabase вместо `cloneStore`/`jobStore`.
3. Проверить, что навигация показывает только свои клоны (через RLS).

### Этап 3 — Создание клонов/джобов через Supabase

1. Переписать `POST /api/training`:
   - создаёт `training_jobs` и `clones` в Supabase (с `user_id = auth.uid()`),
   - возвращает `{ jobId, cloneId }`.
2. В Python‑пайплайне обновлять статусы джобов и клонов через Supabase:
   - используя сервисный ключ (`SUPABASE_SERVICE_ROLE_KEY`) или прямой вызов API.
3. Убедиться, что UI статусов (`/training`, `/clones`) читает всё из Supabase.

### Этап 4 — Datasets и Knowledge (RAG)

1. Переписать `/api/datasets`:
   - создание/обновление записи в `datasets` при загрузке/удалении файлов.
2. Переписать `/api/clones/[cloneId]/knowledge`:
   - обновление `clones.knowledge_file`, `clones.rag_index_dir`, `clones.knowledge_count` в Supabase.
3. Убедиться, что вкладка Data отображает знания из Supabase (через `clone`).

### Этап 5 — Интеграции и воркер

1. Переписать `integrationStore` на таблицу `integrations`.
2. Переписать API `/api/clones/[cloneId]/integrations` на Supabase.
3. В `workerManager` использовать сервисного Supabase‑клиента для чтения:
   - клона, джоба, интеграций.
4. Проверить, что Telegram‑бот и другие интеграции корректно работают только с клонов текущего пользователя (через их `cloneId`).

### Этап 6 — Чистка старого кода и миграция

1. Написать один скрипт миграции:
   - прочитать `uploads/data/clones.json` и `uploads/data/jobs.json`,
   - импортировать данные в Supabase (dev/staging).
2. После успешной миграции:
   - удалить `cloneStore.ts`, `jobStore.ts`, `integrationStore.ts`,
   - удалить JSON‑файлы в `uploads/data`.

---

## 7. Резюме

- Supabase не хранит модели и файлы, он хранит **метаданные** и отвечает за:
  - пользователей и авторизацию,
  - привязку клонов/датасетов/джобов к `user_id`,
  - безопасность через RLS.
- Python‑пайплайн и файловая структура `uploads/` остаются как есть.
- Next.js становится thin‑client поверх Supabase:
  - всё, что сейчас хранится в локальных JSON, уезжает в Postgres,
  - навигация и UI работают поверх данных, фильтрованных по `user_id`.

Этот план можно реализовывать поэтапно, начиная с минимальной интеграции Auth и чтения клонов из Supabase, а затем постепенно переводя создание/обновление всех сущностей на БД. После завершения у платформы будет полноценный multi‑tenant бэкенд без велосипеда.

