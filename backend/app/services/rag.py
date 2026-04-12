from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.core.config import get_settings

settings = get_settings()


def extract_text(filename: str, payload: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md"}:
        return payload.decode("utf-8", errors="ignore")
    if ext == ".pdf":
        reader = PdfReader(BytesIO(payload))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == ".docx":
        document = Document(BytesIO(payload))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise ValueError(f"Unsupported extension: {ext}")


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = start + chunk_size
        chunks.append(normalized[start:end])
        start += chunk_size - overlap
    return chunks


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(str(settings.embedding_model))


@lru_cache
def get_reranker() -> CrossEncoder | None:
    if not settings.reranker_enabled:
        return None
    reranker_path = Path(settings.reranker_model)
    if not reranker_path.exists():
        return None
    return CrossEncoder(str(reranker_path))


@lru_cache
def get_llama_model():
    llm_path = Path(settings.llm_model_path)
    if not llm_path.exists():
        raise FileNotFoundError(f"GGUF model not found: {llm_path}")

    from llama_cpp import Llama

    return Llama(model_path=str(llm_path), n_ctx=settings.llm_n_ctx, verbose=False)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]


def rerank_contexts(question: str, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reranker = get_reranker()
    if not reranker or len(contexts) < 2:
        return contexts[: settings.top_k]

    pairs = [(question, context["content"]) for context in contexts]
    scores = reranker.predict(pairs)
    rescored = []
    for context, score in zip(contexts, scores, strict=True):
        updated = dict(context)
        updated["rerank_score"] = float(score)
        rescored.append(updated)
    rescored.sort(key=lambda item: item["rerank_score"], reverse=True)
    return rescored[: settings.top_k]


def build_prompt(question: str, contexts: list[str]) -> str:
    context_block = "\n\n".join(f"[{idx + 1}] {chunk}" for idx, chunk in enumerate(contexts))
    return (
        "Ты помощник по документам пользователя.\n"
        "Отвечай только по переданному контексту.\n"
        "Если данных недостаточно, скажи это явно.\n"
        "Не придумывай факты и не ссылайся на внешние знания.\n\n"
        f"Контекст:\n{context_block}\n\nВопрос: {question}\nОтвет:"
    )


def generate_answer(question: str, contexts: list[str]) -> str:
    if not contexts:
        return "Недостаточно данных в ваших документах, чтобы ответить на вопрос."

    provider = settings.llm_provider.lower()
    prompt = build_prompt(question, contexts)

    if provider == "llama_cpp":
        try:
            llm = get_llama_model()
            output = llm(
                prompt=prompt,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
            return output["choices"][0]["text"].strip()
        except Exception:
            if not settings.llm_fallback_to_stub:
                raise

    if provider == "transformers":
        from transformers import pipeline

        generator = pipeline("text-generation", model=settings.llm_model_name)
        output = generator(prompt, max_new_tokens=256, do_sample=False)[0]["generated_text"]
        return output.replace(prompt, "").strip()

    # Stub provider for reliable local MVP without heavy model runtime.
    top_context = contexts[0][:900]
    return (
        "Ответ основан на найденных фрагментах документов.\n\n"
        f"Ключевой фрагмент: {top_context}\n\n"
        f"Интерпретация: по вопросу «{question}» система рекомендует опираться на указанный контекст."
    )
