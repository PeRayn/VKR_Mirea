import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Chat, Chunk, FileRecord, Message, User
from app.schemas import AskIn, AskOut, ChatCreateIn, ChatOut, MessageOut
from app.services.rag import (
    LLMGenerationError,
    build_retrieval_query,
    embed_texts,
    generate_answer,
    rerank_contexts,
)
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/chats", tags=["chat"])


def _compact_sources(ranked: list[dict]) -> list[dict]:
    by_file: dict[str, dict] = {}
    order: list[str] = []
    for item in ranked:
        src = item["source"]
        fid = str(src["file_id"])
        if fid not in by_file:
            by_file[fid] = {"file_id": fid, "file_name": src["file_name"]}
            order.append(fid)
    return [by_file[fid] for fid in order]


@router.post("", response_model=ChatOut)
async def create_chat(
    payload: ChatCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = Chat(user_id=user.id, title=payload.title)
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return ChatOut.model_validate(chat, from_attributes=True)


@router.get("", response_model=list[ChatOut])
async def list_chats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[ChatOut]:
    chats = (await db.scalars(select(Chat).where(Chat.user_id == user.id).order_by(Chat.created_at.desc()))).all()
    return [ChatOut.model_validate(chat, from_attributes=True) for chat in chats]


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    chat = await db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    await db.delete(chat)
    await db.commit()


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def list_messages(
    chat_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    chat = await db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    messages = (
        await db.scalars(
            select(Message).where(Message.chat_id == chat.id, Message.user_id == user.id).order_by(Message.created_at.asc())
        )
    ).all()
    return [MessageOut.model_validate(message, from_attributes=True) for message in messages]


@router.post("/{chat_id}/ask", response_model=AskOut)
async def ask(
    chat_id: uuid.UUID,
    payload: AskIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AskOut:
    chat = await db.scalar(select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    prior = (
        await db.scalars(
            select(Message)
            .where(Message.chat_id == chat.id, Message.user_id == user.id)
            .order_by(Message.created_at.asc())
        )
    ).all()
    chat_history = [{"role": m.role, "content": m.content} for m in prior]

    retrieval_query = build_retrieval_query(payload.question, chat_history or None)
    query_vector = embed_texts([retrieval_query])[0]
    distance_col = Chunk.embedding.cosine_distance(query_vector).label("distance")
    matched = (
        await db.execute(
            select(Chunk, FileRecord, distance_col)
            .join(FileRecord, FileRecord.id == Chunk.file_id)
            .where(Chunk.user_id == user.id, FileRecord.user_id == user.id)
            .order_by(distance_col)
            .limit(settings.retrieval_top_k)
        )
    ).all()

    retrieved_contexts: list[dict] = []
    for chunk, file_record, distance in matched:
        retrieved_contexts.append(
            {
                "content": chunk.content,
                "cosine_distance": float(distance),
                "source": {
                    "file_id": str(file_record.id),
                    "file_name": file_record.original_name,
                    "chunk_id": str(chunk.id),
                    "chunk_index": chunk.chunk_index,
                },
            }
        )

    ranked_contexts = rerank_contexts(retrieval_query, retrieved_contexts)
    sources = _compact_sources(ranked_contexts)
    try:
        answer = generate_answer(payload.question, ranked_contexts, chat_history or None)
    except LLMGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    db.add(Message(chat_id=chat.id, user_id=user.id, role="user", content=payload.question))
    db.add(Message(chat_id=chat.id, user_id=user.id, role="assistant", content=answer, sources=sources))
    await db.commit()

    return AskOut(answer=answer, sources=sources, chat_id=chat.id)
