import base64
from pathlib import Path

import pytest

from neuroca.tools.caching import FileCache, _sign_payload, _verify_and_extract


def _encode_key(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def test_file_cache_rejects_tampered_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEUROCA_CACHE_SIGNING_KEY", _encode_key(b"A" * 32))
    cache = FileCache(cache_dir=str(tmp_path))
    cache.set("example", {"value": 1})

    cache_path = next(tmp_path.glob("*.cache"))
    original = cache_path.read_bytes()
    tampered = original[:-1] + bytes([original[-1] ^ 0xFF])
    cache_path.write_bytes(tampered)

    assert cache.get("example") is None
    assert not cache_path.exists()
    stats = cache.get_stats()
    assert stats["misses"] == 1


def test_file_cache_uses_environment_signing_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEUROCA_CACHE_SIGNING_KEY", _encode_key(b"B" * 32))
    cache = FileCache(cache_dir=str(tmp_path))
    cache.set("alpha", ["value"])

    # Simulate a new process reading the same cache directory.
    reloaded = FileCache(cache_dir=str(tmp_path))
    assert reloaded.get("alpha") == ["value"]


def test_file_cache_rejects_entries_signed_with_new_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEUROCA_CACHE_SIGNING_KEY", _encode_key(b"C" * 32))
    cache = FileCache(cache_dir=str(tmp_path))
    cache.set("beta", "secret")

    monkeypatch.setenv("NEUROCA_CACHE_SIGNING_KEY", _encode_key(b"D" * 32))
    reloaded = FileCache(cache_dir=str(tmp_path))
    assert reloaded.get("beta") is None


def test_signed_payload_verification_detects_tampering() -> None:
    key = b"E" * 32
    payload = b"payload"

    signed = _sign_payload(key, payload)
    assert _verify_and_extract(key, signed) == payload

    tampered = signed[:-1] + bytes([signed[-1] ^ 0xFF])
    with pytest.raises(ValueError):
        _verify_and_extract(key, tampered)

    with pytest.raises(ValueError):
        _verify_and_extract(b"F" * 32, signed)
