import logging
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import Chunk, FileRecord, User
from app.schemas import FileOut
from app.services.rag import chunk_text, embed_texts, extract_text
from app.services.storage import storage
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/files", tags=["files"])
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def _content_disposition(disposition: str, filename: str) -> str:
    try:
        filename.encode("latin-1")
        safe = filename.replace('"', "_")
        return f'{disposition}; filename="{safe}"'
    except UnicodeEncodeError:
        ext = Path(filename).suffix
        ascii_fallback = "".join(c if ord(c) < 128 else "_" for c in Path(filename).stem) or "file"
        ascii_fallback = f"{ascii_fallback}{ext}" if ext else ascii_fallback
        encoded = quote(filename, safe="")
        return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'


def _validate_upload(upload: UploadFile, size_bytes: int) -> None:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file extension")
    if size_bytes > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max is {settings.max_upload_mb}MB",
        )
    if size_bytes == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file is not allowed")


@router.post("/upload", response_model=FileOut)
async def upload_file(
    upload: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    content = await upload.read()
    _validate_upload(upload, len(content))

    stored_name = storage.save(user.id, upload.filename or "unnamed", content)
    file_record = FileRecord(
        user_id=user.id,
        original_name=upload.filename or stored_name,
        stored_name=stored_name,
        mime_type=upload.content_type or "application/octet-stream",
        size_bytes=len(content),
    )
    db.add(file_record)
    await db.flush()

    try:
        text = extract_text(file_record.original_name, content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse document content",
        ) from exc
    chunks = chunk_text(text)
    if chunks:
        embeddings = embed_texts(chunks)
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            db.add(
                Chunk(
                    user_id=user.id,
                    file_id=file_record.id,
                    chunk_index=idx,
                    content=chunk,
                    embedding=embedding,
                )
            )

    await db.commit()
    await db.refresh(file_record)
    logger.info("File uploaded: id=%s user=%s name='%s' size=%d chunks=%d", file_record.id, user.email, file_record.original_name, len(content), len(chunks))
    return FileOut.model_validate(file_record, from_attributes=True)


@router.get("", response_model=list[FileOut])
async def list_files(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[FileOut]:
    records = (await db.scalars(select(FileRecord).where(FileRecord.user_id == user.id).order_by(FileRecord.created_at.desc()))).all()
    return [FileOut.model_validate(record, from_attributes=True) for record in records]


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    file_record = await db.scalar(
        select(FileRecord).where(FileRecord.id == file_id, FileRecord.user_id == user.id)
    )
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    payload = storage.read(user.id, file_record.stored_name)
    return StreamingResponse(
        iter([payload]),
        media_type=file_record.mime_type,
        headers={"Content-Disposition": _content_disposition("attachment", file_record.original_name)},
    )


@router.get("/{file_id}/content")
async def file_content(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    file_record = await db.scalar(
        select(FileRecord).where(FileRecord.id == file_id, FileRecord.user_id == user.id)
    )
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    payload = storage.read(user.id, file_record.stored_name)
    try:
        text = extract_text(file_record.original_name, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from file",
        ) from exc
    return PlainTextResponse(text)


@router.get("/{file_id}/view")
async def view_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    file_record = await db.scalar(
        select(FileRecord).where(FileRecord.id == file_id, FileRecord.user_id == user.id)
    )
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    payload = storage.read(user.id, file_record.stored_name)
    return StreamingResponse(
        iter([payload]),
        media_type=file_record.mime_type,
        headers={"Content-Disposition": _content_disposition("inline", file_record.original_name)},
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    file_record = await db.scalar(
        select(FileRecord).where(FileRecord.id == file_id, FileRecord.user_id == user.id)
    )
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    await db.execute(delete(Chunk).where(Chunk.file_id == file_record.id))
    await db.delete(file_record)
    storage.delete(user.id, file_record.stored_name)
    await db.commit()
    logger.info("File deleted: id=%s user=%s name='%s'", file_id, user.email, file_record.original_name)
    return {"status": "ok"}
