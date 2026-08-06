"""API smoke in a clean subprocess (fresh settings/engine, no import-cache issues)."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


def test_health_and_install_status(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = tmp_path / "storage"
    storage.mkdir()
    script = textwrap.dedent(
        f"""
        from cryptography.fernet import Fernet
        import os
        os.environ["APP_ENV"] = "test"
        os.environ["DB_ENGINE"] = "sqlite"
        os.environ["DATABASE_URL"] = "sqlite:///{db_path}"
        os.environ["STORAGE_ROOT"] = "{storage}"
        os.environ["SECRET_KEY"] = "test-secret-key-please-change"
        os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-please-change"
        os.environ["DATA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        os.environ["RATE_LIMIT_ENABLED"] = "false"

        from fastapi.testclient import TestClient
        from app.main import app, on_startup

        on_startup()
        with TestClient(app) as client:
            h = client.get("/health")
            assert h.status_code == 200, h.text
            assert h.json()["status"] == "ok"
            s = client.get("/api/v1/install/status")
            assert s.status_code == 200, s.text
            body = s.json()
            assert "installed" in body
            assert body.get("db_engine") == "sqlite"
        """
    )
    env = {
        **dict(**{k: v for k, v in __import__("os").environ.items()}),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    }
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
