"""Unit tests for API key generation, parsing, hashing, and verification."""

from __future__ import annotations

import pytest

from app.security import api_keys as keys


def test_generate_round_trip(settings) -> None:
    g = keys.generate("test")
    assert g.plaintext.startswith("rpg_test_")
    assert g.environment == "test"
    assert len(g.key_id) == 16
    assert g.last_four == g.plaintext[-4:]
    parsed = keys.parse(g.plaintext)
    assert parsed.environment == "test"
    assert parsed.key_id == g.key_id
    assert keys.verify(parsed.secret, g.key_hash) is True


def test_generate_live_prefix(settings) -> None:
    g = keys.generate("live")
    assert g.plaintext.startswith("rpg_live_")
    assert g.key_prefix == "rpg_live_"


def test_invalid_environment_rejected(settings) -> None:
    with pytest.raises(ValueError):
        keys.generate("staging")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-a-key",
        "rpg_live",
        "pk_live_abc_def",
        "rpg_live_short_short",  # wrong lengths
    ],
)
def test_parse_rejects_garbage(settings, bad: str) -> None:
    with pytest.raises(keys.InvalidApiKey):
        keys.parse(bad)


def test_tampered_secret_fails_verify(settings) -> None:
    g = keys.generate("test")
    p = keys.parse(g.plaintext)
    tampered = p.secret[:-1] + ("A" if p.secret[-1] != "A" else "B")
    assert keys.verify(tampered, g.key_hash) is False


def test_pepper_dependence(settings, monkeypatch) -> None:
    g = keys.generate("test")
    p = keys.parse(g.plaintext)

    # Swap pepper → verification must fail.
    from app.config import get_settings

    monkeypatch.setenv("API_KEY_PEPPER", "11" * 32)
    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        assert keys.verify(p.secret, g.key_hash) is False
    finally:
        monkeypatch.setenv("API_KEY_PEPPER", "deadbeefcafef00d" * 4)
        get_settings.cache_clear()  # type: ignore[attr-defined]


def test_environment_in_prefix(settings) -> None:
    g_test = keys.generate("test")
    g_live = keys.generate("live")
    assert keys.parse(g_test.plaintext).environment == "test"
    assert keys.parse(g_live.plaintext).environment == "live"
