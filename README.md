# Smart Disk

`Smart Disk` - MVP облачного диска с приватным RAG-чатом по документам пользователя.

## Что внутри

- Backend: FastAPI + async SQLAlchemy + JWT
- Frontend: React + Vite
- DB: PostgreSQL + pgvector
- Embeddings: локальная `models/bge-m3`
- Reranker: локальная `models/bge-reranker-base`
- LLM: локальная `models/Qwen3-4B-Q4_K_M.gguf` через `llama.cpp`
- Хранилище файлов: локальное, через абстракцию для будущего S3

## Как работает RAG

1. Пользователь логинится и получает JWT.
2. Загружает `pdf/docx/txt/md`.
3. Backend извлекает текст, режет на чанки и считает embeddings через `bge-m3`.
4. Чанки сохраняются в PostgreSQL с `user_id`, `file_id` и `pgvector`.
5. При вопросе из чата выполняется vector search по документам текущего пользователя.
6. Затем найденные чанки дополнительно пересортируются через `bge-reranker-base`.
7. Лучший контекст уходит в `Qwen3-4B-Q4_K_M.gguf`, ответ и `sources` сохраняются в БД.

## Структура

```text
.
├── backend/
│   ├── app/
│   ├── migrations/001_initial.sql
│   ├── scripts/smoke_test.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── .env.example
│   └── package.json
├── models/
│   ├── Qwen3-4B-Q4_K_M.gguf
│   ├── bge-m3/
│   └── bge-reranker-base/
├── run_dev.py
└── README.md
```

## Модели

Проект уже настроен под такие локальные пути:

- `models/Qwen3-4B-Q4_K_M.gguf`
- `models/bge-m3`
- `models/bge-reranker-base`

Под `bge-m3` используется размерность эмбеддингов `1024`, поэтому initial migration настроена на `VECTOR(1024)`.

## Подготовка окружения на macOS

Нужно установить:

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+ с расширением `pgvector`

Пример через Homebrew:

```bash
brew install postgresql@15
brew services start postgresql@15
```

## Установка backend

```bash
cd /Users/perayn/envs/VKR_Mirea/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Установка frontend

```bash
cd /Users/perayn/envs/VKR_Mirea/frontend
npm install
cp .env.example .env
```

## Инициализация БД

```bash
createdb smartdisk
psql "postgresql://smartdisk:smartdisk@localhost:5432/smartdisk" -f /Users/perayn/envs/VKR_Mirea/backend/migrations/001_initial.sql
```

Если у вас другие пользователь, пароль или имя БД, поправьте `DATABASE_URL` в `backend/.env`.

## Запуск одной командой

После подготовки `.env`, базы и моделей можно стартовать проект так:

```bash
cd /Users/perayn/envs/VKR_Mirea
.venv/bin/python run_dev.py
```

`run_dev.py`:

- проверяет `backend/.env` и `frontend/.env`
- проверяет наличие `Qwen`, `bge-m3` и `bge-reranker-base`
- запускает backend на `http://localhost:8000`
- ждет `GET /ready`
- запускает frontend на `http://localhost:5173`
- останавливает оба процесса по `Ctrl+C`

## Ручной запуск

Backend:

```bash
cd /Users/perayn/envs/VKR_Mirea/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd /Users/perayn/envs/VKR_Mirea/frontend
npm run dev
```

## Проверка

Health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Smoke test:

```bash
cd /Users/perayn/envs/VKR_Mirea/backend
source .venv/bin/activate
python scripts/smoke_test.py
```

Ожидаемый результат:

```text
SMOKE TEST PASSED
```

## Основные env-переменные

```env
MODELS_ROOT=../models
EMBEDDING_MODEL=../models/bge-m3
EMBEDDING_DIM=1024
RERANKER_ENABLED=true
RERANKER_MODEL=../models/bge-reranker-base
LLM_PROVIDER=llama_cpp
LLM_MODEL_PATH=../models/Qwen3-4B-Q4_K_M.gguf
LLM_FALLBACK_TO_STUB=true
```

## Что улучшить дальше

- вынести миграции в Alembic
- сделать фоновую очередь для индексации файлов
- добавить потоковый ответ чата
- вынести storage в S3/MinIO adapter
- добавить полноценные integration/e2e тесты
- усилить observability, rate limit и refresh tokens
# Smart Disk (RAG Cloud Storage MVP)

Smart Disk is an MVP cloud storage app with private RAG chat over user files.

## Stack

- Backend: FastAPI (Python 3.12)
- Frontend: React + Vite
- DB: PostgreSQL + pgvector
- Embeddings: sentence-transformers
- LLM provider options: `stub`, `llama_cpp`, `transformers`
- File storage: local filesystem with a storage abstraction for future S3 migration

## Architecture

1. User authenticates and receives JWT.
2. User uploads a file (`pdf/docx/txt/md`).
3. Backend extracts text, chunks it, computes embeddings, and stores chunks in PostgreSQL with pgvector.
4. Chat question is embedded and searched in `chunks` by vector distance scoped by `user_id`.
5. LLM generates answer from retrieved contexts only.
6. Answer and sources are stored in chat history.

## Project layout

```text
.
├── backend
│   ├── app
│   │   ├── core
│   │   │   └── config.py
│   │   ├── routers
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   └── files.py
│   │   ├── services
│   │   │   ├── rag.py
│   │   │   └── storage.py
│   │   ├── auth.py
│   │   ├── db.py
│   │   ├── deps.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── migrations
│   │   └── 001_initial.sql
│   ├── scripts
│   │   └── smoke_test.py
│   ├── .env.example
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── pages
│   │   │   ├── AuthPage.jsx
│   │   │   ├── ChatPage.jsx
│   │   │   └── FilesPage.jsx
│   │   ├── api.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Prerequisites (macOS)

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+ with pgvector extension

Example with Homebrew:

```bash
brew install postgresql@15
brew services start postgresql@15
```

Install pgvector extension (example):

```bash
psql postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Backend setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Create DB and run migration:

```bash
createdb smartdisk
psql "postgresql://smartdisk:smartdisk@localhost:5432/smartdisk" -f migrations/001_initial.sql
```

If local role/database differs, update `DATABASE_URL` in `backend/.env`.

Run backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Health checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env
```

Run frontend:

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Smoke test (e2e-ish API flow)

Backend must be running.

```bash
cd backend
source .venv/bin/activate
python scripts/smoke_test.py
```

Expected output:

```text
SMOKE TEST PASSED
```

## Notes

- `LLM_PROVIDER=stub` is default for lightweight local MVP.
- To switch to `llama_cpp` or `transformers`, set provider fields in `backend/.env`.
- File access and vector search are strictly scoped to `user_id` in endpoints and SQL queries.
# Smart Disk (RAG Cloud Storage MVP)

MVP веб-приложения "Умный диск": пользователь загружает документы, они индексируются в pgvector, затем пользователь задает вопросы в чате и получает ответы только по своим файлам.

## Архитектура

- **Backend (`backend/`)**: FastAPI + async SQLAlchemy + JWT auth.
- **База данных**: PostgreSQL + pgvector (`docker-compose.yml`).
- **RAG pipeline**:
  - извлечение текста из `pdf/docx/txt/md`,
  - чанкинг текста,
  - эмбеддинги через `sentence-transformers`,
  - векторный поиск `cosine distance` в pgvector,
  - генерация ответа (`stub`/`llama_cpp`/`transformers`).
- **Frontend (`frontend/`)**: React + Vite (страницы Auth, Files, Chat).
- **Хранение файлов**: локальный диск (`FILES_ROOT`) через абстракцию `LocalFileStorage`.

## Структура

```text
.
├── backend
│   ├── app
│   │   ├── core/config.py
│   │   ├── routers/{auth.py,files.py,chat.py}
│   │   ├── services/{storage.py,rag.py}
│   │   ├── auth.py
│   │   ├── db.py
│   │   ├── deps.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── migrations/001_initial.sql
│   ├── scripts/smoke_test.py
│   ├── .env.example
│   └── requirements.txt
├── frontend
│   ├── src/pages/{AuthPage.jsx,FilesPage.jsx,ChatPage.jsx}
│   ├── src/{App.jsx,api.js,main.jsx}
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env.example
├── docker-compose.yml
└── README.md
```

## Setup backend (macOS)

```bash
cd /Users/perayn/envs/VKR_Mirea
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

### Запуск PostgreSQL + pgvector

```bash
docker compose up -d postgres
```

### Применение initial schema

```bash
psql "postgresql://smartdisk:smartdisk@localhost:5432/smartdisk" -f backend/migrations/001_initial.sql
```

### Запуск backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## Setup frontend

```bash
cd /Users/perayn/envs/VKR_Mirea/frontend
npm install
cp .env.example .env
```

## Запуск frontend

```bash
cd /Users/perayn/envs/VKR_Mirea/frontend
npm run dev
```

Frontend будет доступен на `http://localhost:5173`, backend на `http://localhost:8000`.

## Smoke test (e2e API)

1. Убедиться, что backend и postgres запущены.
2. Выполнить:

```bash
cd /Users/perayn/envs/VKR_Mirea
source .venv/bin/activate
python backend/scripts/smoke_test.py
```

Ожидаемый результат: `SMOKE TEST PASSED`.

## API (основные endpoint-ы)

- Auth: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- Files: `POST /files/upload`, `GET /files`, `GET /files/{id}/download`, `DELETE /files/{id}`
- Chats: `POST /chats`, `GET /chats`, `GET /chats/{id}/messages`, `POST /chats/{id}/ask`
- Infra: `GET /health`, `GET /ready`

## Переключение на реальные LLM

- `LLM_PROVIDER=stub` (по умолчанию): быстрый и стабильный MVP.
- `LLM_PROVIDER=llama_cpp`: требуется `LLM_MODEL_PATH=/path/to/model.gguf`.
- `LLM_PROVIDER=transformers`: используется `LLM_MODEL_NAME`.

Для production рекомендуется вынести индексацию и inference в фоновые воркеры (Celery/RQ/Arq) и добавить очередь.
