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

чередь.
