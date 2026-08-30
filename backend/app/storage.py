"""File storage abstraction for uploaded/generated documents.

Files are addressed by POSIX-style relative "keys" such as
``templates/1/document.pdf``. Keys are validated to reject absolute paths
and any ``..`` segment so callers cannot escape the storage root.
"""

from pathlib import Path
from typing import Protocol

from app.config import Settings


class FileStorage(Protocol):
    """Storage backend for reading and writing files addressed by key."""

    def save(self, key: str, data: bytes) -> None:
        """Write ``data`` to ``key``, creating parent directories as needed."""
        ...

    def open(self, key: str) -> bytes:
        """Return the bytes stored at ``key``, raising FileNotFoundError if absent."""
        ...

    def exists(self, key: str) -> bool:
        """Return whether ``key`` refers to an existing file."""
        ...

    def delete(self, key: str) -> None:
        """Remove the file at ``key``, if it exists."""
        ...


def _validate_key(key: str) -> None:
    """Raise ValueError if ``key`` is absolute or contains a ``..`` segment."""
    if not key:
        raise ValueError("Storage key must not be empty")
    if key.startswith("/") or key.startswith("\\"):
        raise ValueError(f"Storage key must be relative: {key!r}")
    if Path(key).drive:
        raise ValueError(f"Storage key must be relative: {key!r}")
    segments = key.replace("\\", "/").split("/")
    if ".." in segments:
        raise ValueError(f"Storage key must not contain '..' segments: {key!r}")


class LocalVolumeStorage:
    """Stores files on a local filesystem volume rooted at ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _resolve(self, key: str) -> Path:
        _validate_key(key)
        return self.root / key

    def save(self, key: str, data: bytes) -> None:
        """Write ``data`` to ``key``, creating parent directories as needed."""
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def open(self, key: str) -> bytes:
        """Return the bytes stored at ``key``, raising FileNotFoundError if absent."""
        path = self._resolve(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        """Return whether ``key`` refers to an existing file."""
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        """Remove the file at ``key``, if it exists."""
        path = self._resolve(key)
        path.unlink(missing_ok=True)


def get_storage(settings: Settings) -> FileStorage:
    """Return the configured FileStorage backend, rooted at ``settings.data_dir``."""
    return LocalVolumeStorage(Path(settings.data_dir))
