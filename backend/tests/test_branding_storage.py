"""Branding storage path helpers."""

from pathlib import Path

from app.infrastructure.branding_storage import default_logo_path, resolve_logo_path


def test_default_logos_exist() -> None:
    assert default_logo_path("icon").is_file()
    assert default_logo_path("full").is_file()


def test_resolve_falls_back_to_default(tmp_path: Path, monkeypatch) -> None:
    from app.config import Settings

    settings = Settings(
        storage_root=str(tmp_path / "storage"),
        data_encryption_key="dGVzdC1rZXktMzItYnl0ZXMtZXhjaGFuZ2UhIQ==",
    )
    path = resolve_logo_path(settings, tenant_id=1, kind="icon")
    assert path == default_logo_path("icon")
