import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


class FileStorage(ABC):
    @abstractmethod
    def save(self, user_id: uuid.UUID, original_name: str, data: bytes) -> str:
        pass

    @abstractmethod
    def read(self, user_id: uuid.UUID, stored_name: str) -> bytes:
        pass

    @abstractmethod
    def delete(self, user_id: uuid.UUID, stored_name: str) -> None:
        pass


class LocalFileStorage(FileStorage):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def user_dir(self, user_id: uuid.UUID) -> Path:
        path = self.root / str(user_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, user_id: uuid.UUID, original_name: str, data: bytes) -> str:
        suffix = Path(original_name).suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        full_path = self.user_dir(user_id) / stored_name
        full_path.write_bytes(data)
        return stored_name

    def read(self, user_id: uuid.UUID, stored_name: str) -> bytes:
        return (self.user_dir(user_id) / stored_name).read_bytes()

    def delete(self, user_id: uuid.UUID, stored_name: str) -> None:
        path = self.user_dir(user_id) / stored_name
        if path.exists():
            path.unlink()


def build_storage() -> FileStorage:
    # The app currently ships with local storage for MVP.
    # Keep constructor-based factory to simplify switch to S3 later.
    return LocalFileStorage(settings.files_root)


storage = build_storage()
