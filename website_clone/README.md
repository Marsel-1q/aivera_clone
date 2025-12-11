# AIVERA — платформа цифровых AI‑клонов (Supabase + Next.js 15)

Веб‑приложение для создания, обучения и тестирования персональных AI‑клонов. Фронт — Next.js 15 / React 19 / Tailwind, бэкенд‑метаданные и авторизация — **Supabase** (Postgres + Auth + RLS). Тяжёлые артефакты (датасеты, LoRA, RAG) остаются на локальной файловой системе и обслуживаются Python‑пайплайном (`dataset_pipeline/cli.py`, `train_qlora.py`, `rag/index_builder.py`, `chat_with_lora.py`).

## Стек
- Next.js 15 (App Router), TypeScript, Tailwind CSS (v4), Shadcn UI, Lucide.
- Supabase: Auth + Postgres + RLS для изоляции данных пользователей.
- Python: QLoRA обучение и RAG индексация (локально в `uploads/`).

## Структура
```
src/
  app/
    (auth)/login, (auth)/signup
    (dashboard)/...          # защищённые маршруты (проверка сессии)
    api/                     # API с проверкой Supabase-сессии
  components/                # UI и layout (Sidebar, Header с Logout)
  lib/
    supabase/                # серверный/клиентский клиенты Supabase
    repositories/            # CRUD для clones/training_jobs через Supabase
  uploads/                   # локальные датасеты/джобы/индексы
scripts/                     # chat_with_lora.py, clone_worker.js
```

## Что реализовано сейчас
- **Auth Supabase**: реальная регистрация/логин. Дашборд защищён серверной проверкой сессии (нет сессии → `/login`).
- **Выход**: кнопка Logout в хэдере дашборда вызывает `supabase.auth.signOut()` и переводит на `/login`. Дополнительно, заход на главную (`/`) выполняет silent logout, чтобы после ухода с дашборда всегда требовался повторный вход.
- **RLS и доступ**: все ключевые API проверяют сессию Supabase и возвращают 401 при отсутствии пользователя:
  - `/api/clones`, `/api/clones/[cloneId]`
  - `/api/training`, `/api/training/[id]`
  - `/api/datasets`
  - `/api/clones/[cloneId]/knowledge`
- **Clones/Jobs/Datasets**: метаданные хранятся в Supabase (через `repositories/*`), а файлы — в `uploads/`. Все операции привязаны к `user_id` и фильтруются RLS.
- **RAG привязка к cloneId**: чат и воркер используют `clone.ragIndexDir` (или job.ragIndexDir) — удалённые знания не попадают в ответы после пересборки.
- **Обучение**: `POST /api/training` создаёт записи в Supabase и запускает пайплайн, если `ENABLE_REAL_TRAINING=true`. Без флага включается симуляция статусов.

## Поток обучения (реальный режим)
1) Загрузить датасет во вкладке Data/мастер создания — файлы падают в `uploads/datasets/<datasetId>` и видны только авторизованному пользователю.  
2) Нажать Start Training (`/api/training`): в Supabase создаются `training_job` и `clone`, пайплайн пишет артефакты в `uploads/jobs/<jobId>/...`.  
3) По завершении обновляются статус клона и пути к RAG/адаптеру.  
4) Чат/воркер используют свежие пути из Supabase.

## Сессии и безопасность
- Сессия хранится в cookies Supabase. Для полного выхода используйте Logout или просто зайдите на `/` (происходит авто signOut).  
- Без сессии защищённые маршруты (dashboard) недоступны; API возвращают 401, а не скрытые 404.

## Запуск
1) `.env.local` в `website_clone/`:
```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...   # только на сервере
ENABLE_REAL_TRAINING=true       # чтобы запускать Python-пайплайн
```
2) Установить deps: `npm install`.  
3) Запуск dev: `npm run dev` (Python окружение и зависимости для `dataset_pipeline` должны быть готовы).

## Текущее ограничение (логи/админ)
- Доступ к логам джобов из curl без сессии невозможен из‑за RLS. Для административного чтения нужен отдельный handler с сервисным ключом или авторизованный запрос из браузера.
