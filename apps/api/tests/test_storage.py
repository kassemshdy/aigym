import pytest

from app import storage


def test_save_read_delete_round_trip() -> None:
    key = storage.save(b"fake-jpeg-bytes", "image/jpeg")
    assert key.endswith(".jpg")

    assert storage.read(key) == b"fake-jpeg-bytes"
    assert storage.content_type_for(key) == "image/jpeg"

    storage.delete(key)
    assert storage.read(key) is None


def test_delete_is_idempotent() -> None:
    key = storage.save(b"x", "image/png")
    storage.delete(key)
    storage.delete(key)  # must not raise the second time


def test_save_rejects_unsupported_content_type() -> None:
    with pytest.raises(storage.UnsupportedContentType):
        storage.save(b"not an image", "application/pdf")


def test_read_rejects_a_key_shaped_for_path_traversal() -> None:
    with pytest.raises(storage.InvalidKey):
        storage.read("../../../etc/passwd")


def test_delete_rejects_a_key_shaped_for_path_traversal() -> None:
    with pytest.raises(storage.InvalidKey):
        storage.delete("../../../etc/passwd.jpg")


def test_read_missing_key_returns_none_not_an_error() -> None:
    assert storage.read("00000000000000000000000000000000.jpg") is None
