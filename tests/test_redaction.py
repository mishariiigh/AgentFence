"""Tests for the core redaction helpers."""

from __future__ import annotations

from agentfence_core.redaction import redact


def test_redacts_openai_key() -> None:
    out = redact("key: sk-proj-abcdefghij1234567890ABCD")
    assert "sk-proj-abcdefghij1234567890ABCD" not in out
    assert "[REDACTED]" in out


def test_redacts_anthropic_key() -> None:
    out = redact("sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234")
    assert "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234" not in out


def test_redacts_key_value_pair() -> None:
    out = redact('api_key = "supersecretvalue123"')
    assert "supersecretvalue123" not in out
    assert "api_key" in out  # key name preserved for context


def test_keeps_normal_text() -> None:
    text = "The quick brown fox reads docs/*.md"
    assert redact(text) == text


def test_redacts_bearer_token() -> None:
    out = redact("Authorization: Bearer abcdefghijklmnop123456789")
    assert "abcdefghijklmnop123456789" not in out
