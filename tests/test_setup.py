"""Tests for Cloudflare setup helpers."""

from pathlib import Path

from ai_image_indexer.cloudflare.setup import (
    _looks_like_account_id,
    _parse_wrangler_toml,
    project_env_path,
    write_env_file,
)


def test_looks_like_account_id():
    assert _looks_like_account_id("a" * 32)
    assert not _looks_like_account_id("short")
    assert not _looks_like_account_id("g" * 32)


def test_parse_wrangler_toml(tmp_path: Path):
    config = tmp_path / "default.toml"
    config.write_text(
        'oauth_token = "secret-token"\naccount_id = "abcd1234abcd1234abcd1234abcd1234"\n',
        encoding="utf-8",
    )
    data = _parse_wrangler_toml(config)
    assert data["oauth_token"] == "secret-token"
    assert data["account_id"] == "abcd1234abcd1234abcd1234abcd1234"


def test_write_env_file(tmp_path: Path):
    env_path = tmp_path / ".env"
    write_env_file(env_path, "abcd1234abcd1234abcd1234abcd1234", "token-value")
    text = env_path.read_text(encoding="utf-8")
    assert "CLOUDFLARE_ACCOUNT_ID=abcd1234abcd1234abcd1234abcd1234" in text
    assert "CLOUDFLARE_API_TOKEN=token-value" in text
    assert "AI_IMAGE_INDEXER_VISION_MODEL=" in text


def test_project_env_path_prefers_existing(tmp_path: Path, monkeypatch):
    existing = tmp_path / ".env"
    existing.write_text("x=1", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert project_env_path() == existing
