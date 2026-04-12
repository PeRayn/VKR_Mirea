import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Chat, Chunk, FileRecord, Message, User
from app.schemas import AskIn, AskOut, ChatCreateIn, ChatOut, MessageOut
from app.services.rag import embed_texts, generate_answer, rerank_contexts
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/chats", tags=["chat"])


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

    query_vector = embed_texts([payload.question])[0]
    matched = (
        await db.execute(
            select(Chunk, FileRecord)
            .join(FileRecord, FileRecord.id == Chunk.file_id)
            .where(Chunk.user_id == user.id, FileRecord.user_id == user.id)
            .order_by(Chunk.embedding.cosine_distance(query_vector))
            .limit(settings.retrieval_top_k)
        )
    ).all()

    retrieved_contexts: list[dict] = []
    for chunk, file_record in matched:
        retrieved_contexts.append(
            {
                "content": chunk.content,
                "source": {
                    "file_id": str(file_record.id),
                    "file_name": file_record.original_name,
                    "chunk_id": str(chunk.id),
                    "chunk_index": chunk.chunk_index,
                },
            }
        )

    ranked_contexts = rerank_contexts(payload.question, retrieved_contexts)
    contexts = [item["content"] for item in ranked_contexts]
    sources = [item["source"] for item in ranked_contexts]
    answer = generate_answer(payload.question, contexts)

    db.add(Message(chat_id=chat.id, user_id=user.id, role="user", content=payload.question))
    db.add(Message(chat_id=chat.id, user_id=user.id, role="assistant", content=answer, sources=sources))
    await db.commit()

    return AskOut(answer=answer, sources=sources, chat_id=chat.id)
