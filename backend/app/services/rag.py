from __future__ import annotations

import logging
import re
from collections import defaultdict
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from docx import Document
from pypdf import PdfReader
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.core.config import get_settings


class LLMGenerationError(Exception):
    """Пустой или недоступный ответ Qwen (llama.cpp); см. лог сервера."""


settings = get_settings()
logger = logging.getLogger(__name__)

# Qwen3 в llama.cpp оборачивает рассуждения в <think>…</think>
_THINK_BLOCK = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think>[\s\S]*", re.IGNORECASE)


def _strip_llm_artifacts(text: str) -> str:
    t = text.strip()
    t = _THINK_BLOCK.sub("", t).strip()
    t = _THINK_OPEN.sub("", t).strip()
    return t


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


# Конец фразы/клаузы: после точки/восклицательного/вопросительного, многоточия, ; или ,
_BOUNDARY_AFTER = re.compile(r"(?:[.!?]{1,3}|\.{3})\s+|;\s+|,\s+")


def _natural_chunk_end(s: str, start: int, hard_end: int, min_len: int) -> int:
    """Индекс конца чанка ≤ hard_end: предпочтительно после .,! ?; или хотя бы после пробела."""
    n = len(s)
    hard_end = min(hard_end, n)
    if hard_end <= start:
        return hard_end
    window = s[start:hard_end]
    best_rel = len(window)
    for m in _BOUNDARY_AFTER.finditer(window):
        if m.end() >= min_len:
            best_rel = m.end()
    if best_rel < len(window):
        return start + best_rel
    sp = window.rfind(" ")
    if sp >= min_len - 1:
        return start + sp + 1
    return hard_end


def _overlap_chunk_start(s: str, prev_end: int, overlap: int, prev_start: int) -> int:
    """Начало следующего чанка с перекрытием ~overlap, без старта с середины слова."""
    target = max(prev_start + 1, prev_end - overlap)
    if target >= prev_end:
        return prev_end
    if target > 0 and s[target - 1] != " ":
        sp = s.find(" ", target, prev_end)
        if sp != -1:
            return sp + 1
    return target


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    n = len(normalized)
    min_len = min(120, max(40, chunk_size // 6))
    chunks: list[str] = []
    start = 0
    while start < n:
        hard_end = min(start + chunk_size, n)
        end = _natural_chunk_end(normalized, start, hard_end, min_len)
        if end <= start:
            end = hard_end
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = _overlap_chunk_start(normalized, end, overlap, start)
        if start >= end:
            start = end
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


_llama_instance = None


def get_llama_model():
    global _llama_instance
    if _llama_instance is not None:
        return _llama_instance
    llm_path = Path(settings.llm_model_path).resolve()
    if not llm_path.exists():
        raise FileNotFoundError(f"GGUF model not found: {llm_path}")

    from llama_cpp import Llama

    logger.info("Loading Qwen GGUF from %s (n_ctx=%d)", llm_path, settings.llm_n_ctx)
    _llama_instance = Llama(model_path=str(llm_path), n_ctx=settings.llm_n_ctx, verbose=False)
    return _llama_instance


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]


def build_retrieval_query(question: str, chat_history: list[dict[str, str]] | None, max_chars: int | None = None) -> str:
    limit = max_chars if max_chars is not None else min(6000, max(2400, settings.llm_n_ctx * 2))
    if not chat_history:
        return question
    lines: list[str] = []
    tail = chat_history[-16:]
    for m in tail:
        label = "Пользователь" if m["role"] == "user" else "Ассистент"
        text = m["content"]
        if m["role"] == "assistant" and len(text) > 600:
            text = text[:600] + "…"
        lines.append(f"{label}: {text}")
    lines.append(f"Пользователь: {question}")
    out = "\n".join(lines)
    if len(out) > limit:
        out = out[-limit:]
    return out


def _filter_by_distance(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    threshold = settings.relevance_max_distance
    return [c for c in contexts if c.get("cosine_distance") is None or c["cosine_distance"] <= threshold]


def rerank_contexts(rerank_query: str, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = _filter_by_distance(contexts)
    if not filtered:
        filtered = contexts[:1]

    reranker = get_reranker()
    if not reranker or len(filtered) < 2:
        return filtered[: settings.top_k]

    pairs = [(rerank_query, context["content"]) for context in filtered]
    scores = reranker.predict(pairs)
    rescored = []
    for context, score in zip(filtered, scores, strict=True):
        updated = dict(context)
        updated["rerank_score"] = float(score)
        rescored.append(updated)
    rescored.sort(key=lambda item: item["rerank_score"], reverse=True)

    min_score = settings.reranker_min_score
    top = rescored[: settings.top_k]
    relevant = [c for c in top if c["rerank_score"] >= min_score]
    return relevant if relevant else top[:1]


def _truncate_snippet(text: str, max_len: int = 380) -> str:
    t = " ".join(text.split())
    if len(t) <= max_len:
        return t
    window = t[:max_len]
    low = max(0, max_len - 220)
    best = -1
    for sep in (". ", "! ", "? ", "; ", ", "):
        i = window.rfind(sep)
        if i >= low:
            end = i + len(sep)
            if end > best:
                best = end
    if best > 32:
        return window[:best].rstrip() + "…"
    if " " in window:
        cut = window.rsplit(" ", 1)[0]
        if len(cut) > 24:
            return cut + "…"
    return window.rstrip() + "…"


def _stub_answer(ranked: list[dict[str, Any]]) -> str:
    if not ranked:
        return "Недостаточно данных в ваших документах, чтобы ответить на вопрос."

    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    order: list[str] = []
    for item in ranked:
        fid = str(item["source"]["file_id"])
        if fid not in by_file:
            order.append(fid)
        by_file[fid].append(item)

    blocks: list[str] = []
    for fid in order[:6]:
        items = by_file[fid]
        name = items[0]["source"].get("file_name", "документ")
        merged = max(items, key=lambda x: len(x["content"]))
        snip = _truncate_snippet(merged["content"], 420)
        blocks.append(f"«{name}»\n{snip}")

    body = "\n\n".join(blocks)
    return f"По вашим документам (без языковой модели показываются исходные фрагменты):\n\n{body}"


RAG_SYSTEM_INSTRUCTIONS = (
    "Ты отвечаешь пользователю на русском языке по его личным документам.\n\n"
    "Как писать ответ:\n"
    "- Отвечай на вопрос, обычным разговорным или деловым тоном — как в чате.\n"
    "- Не оформляй ответ как «краткую выжимку», «реферат» или «анализ», если пользователь сам не просил именно так.\n"
    "- Не начинай с шаблонов вроде «На основании предоставленных фрагментов», «Итак, подводя итог» — можно сразу с сути.\n"
    "- Если вопрос приветствие или болтовня без запроса по документам — ответь коротко и дружелюбно, без выдумывания фактов из файлов.\n"
    "- Если вопрос уточняющий и есть переписка ниже — опирайся на неё, не повторяй всё с нуля без нужды.\n"
    "- Используй только факты из блока «Текст из документов». Не добавляй модели, ссылки, цифры и названия, которых нет во фрагментах.\n"
    "- Если во фрагментах нет ответа — скажи это одним-двумя предложениями и при желании предложи, как уточнить вопрос."
)


def _format_rag_user_content(
    question: str, contexts: list[str], chat_history: list[dict[str, str]] | None
) -> str:
    parts_doc = []
    for idx, chunk in enumerate(contexts, start=1):
        parts_doc.append(f"«Фрагмент {idx}»\n{chunk}")
    context_block = "\n\n---\n\n".join(parts_doc)

    hist_block = ""
    if chat_history:
        hlines = []
        for m in chat_history[-16:]:
            label = "Пользователь" if m["role"] == "user" else "Ассистент"
            c = m["content"]
            if m["role"] == "assistant":
                lim = settings.llm_history_assistant_chars
                if len(c) > lim:
                    c = c[:lim] + "…"
            elif m["role"] == "user":
                lim = settings.llm_history_user_chars
                if len(c) > lim:
                    c = c[:lim] + "…"
            hlines.append(f"{label}: {c}")
        hist_block = "Переписка в этом чате:\n" + "\n".join(hlines) + "\n\n---\n\n"

    return (
        f"{hist_block}"
        f"Текст из документов (единственный источник фактов):\n{context_block}\n\n"
        f"Вопрос пользователя: {question}"
    )


def build_prompt(
    question: str, contexts: list[str], chat_history: list[dict[str, str]] | None = None
) -> str:
    """Одиночный текстовый промпт (transformers / запасной completion для llama_cpp)."""
    user_part = _format_rag_user_content(question, contexts, chat_history)
    return f"{RAG_SYSTEM_INSTRUCTIONS}\n\n{user_part}\n\nТвой ответ:"


def generate_answer(
    question: str,
    ranked_contexts: list[dict[str, Any]],
    chat_history: list[dict[str, str]] | None = None,
) -> str:
    contexts = [item["content"] for item in ranked_contexts]
    if not contexts:
        return "Недостаточно данных в ваших документах, чтобы ответить на вопрос."

    provider = settings.llm_provider.lower()
    prompt = build_prompt(question, contexts, chat_history)

    if provider == "llama_cpp":
        try:
            llm = get_llama_model()
            user_content = _format_rag_user_content(question, contexts, chat_history)
            messages = [
                {"role": "system", "content": RAG_SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": user_content},
            ]
            raw_out = llm.create_chat_completion(
                messages=cast(Any, messages),
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                stream=False,
            )
            output = cast(dict[str, Any], raw_out)
            msg = (output["choices"][0].get("message") or {}) if output.get("choices") else {}
            raw = (msg.get("content") or "").strip()
            text = _strip_llm_artifacts(raw)
            if len(text) >= 3:
                return text
            out2 = cast(dict[str, Any], llm(
                prompt=prompt,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            ))
            raw2 = (out2["choices"][0].get("text") or "").strip()
            text2 = _strip_llm_artifacts(raw2)
            if len(text2) >= 3:
                return text2
            raise LLMGenerationError(
                "Модель Qwen вернула пустой ответ. Проверьте GGUF, путь LLM_MODEL_PATH и при необходимости LLM_MAX_TOKENS."
            )
        except LLMGenerationError:
            if settings.llm_fallback_to_stub:
                return _stub_answer(ranked_contexts)
            raise
        except Exception:
            logger.exception("llama_cpp generation failed")
            if not settings.llm_fallback_to_stub:
                raise
            return _stub_answer(ranked_contexts)

    if provider == "transformers":
        from transformers.pipelines import pipeline  # type: ignore[import-untyped]

        gen = pipeline("text-generation", model=settings.llm_model_name)
        raw_out = gen(prompt, max_new_tokens=256, do_sample=False)
        if raw_out is None:
            return _stub_answer(ranked_contexts)
        results = list(raw_out)
        if not results or not isinstance(results[0], dict):
            return _stub_answer(ranked_contexts)
        return str(results[0].get("generated_text", "")).replace(prompt, "").strip()

    return _stub_answer(ranked_contexts)
