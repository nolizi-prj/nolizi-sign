"""Tests for app.storage: LocalVolumeStorage roundtrip and key validation."""

from pathlib import Path

import pytest

from app.config import Settings
from app.storage import LocalVolumeStorage, get_storage


def test_save_open_roundtrip(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    storage.save("templates/1/document.pdf", b"hello world")

    assert storage.open("templates/1/document.pdf") == b"hello world"


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    storage.save("a/b/c/document.pdf", b"data")

    assert (tmp_path / "a" / "b" / "c" / "document.pdf").is_file()


def test_exists_true_after_save(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    storage.save("templates/1/document.pdf", b"data")

    assert storage.exists("templates/1/document.pdf") is True


def test_exists_false_when_missing(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)

    assert storage.exists("templates/1/missing.pdf") is False


def test_delete_removes_file(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)
    storage.save("templates/1/document.pdf", b"data")

    storage.delete("templates/1/document.pdf")

    assert storage.exists("templates/1/document.pdf") is False


def test_open_missing_raises_file_not_found(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)

    with pytest.raises(FileNotFoundError):
        storage.open("templates/1/missing.pdf")


@pytest.mark.parametrize(
    "key",
    [
        "/etc/passwd",
        "../secret.pdf",
        "templates/../../secret.pdf",
        "templates/1/../../../secret.pdf",
        "..",
        "a/b/../c",
    ],
)
def test_rejects_traversal_and_absolute_keys(tmp_path: Path, key: str) -> None:
    storage = LocalVolumeStorage(tmp_path)

    with pytest.raises(ValueError, match=r".+"):
        storage.save(key, b"data")


def test_rejects_traversal_on_open(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)

    with pytest.raises(ValueError, match=r".+"):
        storage.open("../secret.pdf")


def test_rejects_traversal_on_exists(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)

    with pytest.raises(ValueError, match=r".+"):
        storage.exists("../secret.pdf")


def test_rejects_traversal_on_delete(tmp_path: Path) -> None:
    storage = LocalVolumeStorage(tmp_path)

    with pytest.raises(ValueError, match=r".+"):
        storage.delete("../secret.pdf")


def test_get_storage_returns_local_volume_storage_rooted_at_data_dir(tmp_path: Path) -> None:
    settings = Settings(data_dir=str(tmp_path))

    storage = get_storage(settings)

    assert isinstance(storage, LocalVolumeStorage)
    storage.save("templates/1/document.pdf", b"hello")
    assert (tmp_path / "templates" / "1" / "document.pdf").is_file()
