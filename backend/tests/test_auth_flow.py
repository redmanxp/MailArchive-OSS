"""Install → login → must_change_password gate → change password → refresh."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


def test_install_login_change_password_refresh(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.db"
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
        os.environ["FEATURE_PUBLIC_REGISTER"] = "false"

        from fastapi.testclient import TestClient
        from app.main import app, on_startup

        on_startup()
        with TestClient(app) as client:
            st = client.get("/api/v1/install/status")
            assert st.status_code == 200, st.text
            assert st.json()["installed"] is False

            inst = client.post(
                "/api/v1/install",
                json={{
                    "tenant_name": "Acme Test",
                    "tenant_slug": "acme",
                    "admin_name": "Admin",
                    "admin_email": "admin@example.com",
                    "admin_password": "TempPass123!",
                }},
            )
            assert inst.status_code == 200, inst.text
            body = inst.json()
            assert body["must_change_password"] is True
            assert body["temporary_password"] == "TempPass123!"

            bad = client.post(
                "/api/v1/auth/login",
                json={{
                    "email": "admin@example.com",
                    "password": "wrong-password",
                    "tenant_slug": "acme",
                }},
            )
            assert bad.status_code == 401, bad.text

            login = client.post(
                "/api/v1/auth/login",
                json={{
                    "email": "admin@example.com",
                    "password": "TempPass123!",
                    "tenant_slug": "acme",
                }},
            )
            assert login.status_code == 200, login.text
            tok = login.json()
            assert tok["must_change_password"] is True
            access = tok["access_token"]
            refresh = tok["refresh_token"]

            blocked = client.get(
                "/api/v1/admin/users",
                headers={{"Authorization": f"Bearer {{access}}"}},
            )
            assert blocked.status_code == 403, blocked.text

            chg = client.post(
                "/api/v1/auth/change-password",
                headers={{"Authorization": f"Bearer {{access}}"}},
                json={{
                    "current_password": "TempPass123!",
                    "new_password": "NuevaPass456!",
                }},
            )
            assert chg.status_code == 200, chg.text

            login2 = client.post(
                "/api/v1/auth/login",
                json={{
                    "email": "admin@example.com",
                    "password": "NuevaPass456!",
                    "tenant_slug": "acme",
                }},
            )
            assert login2.status_code == 200, login2.text
            tok2 = login2.json()
            assert tok2["must_change_password"] is False
            access2 = tok2["access_token"]

            me = client.get(
                "/api/v1/auth/me",
                headers={{"Authorization": f"Bearer {{access2}}"}},
            )
            assert me.status_code == 200, me.text
            assert me.json()["email"] == "admin@example.com"

            users = client.get(
                "/api/v1/admin/users",
                headers={{"Authorization": f"Bearer {{access2}}"}},
            )
            assert users.status_code == 200, users.text

            ref = client.post(
                "/api/v1/auth/refresh",
                json={{"refresh_token": tok2["refresh_token"]}},
            )
            assert ref.status_code == 200, ref.text
            assert "access_token" in ref.json()

            # old refresh from before password change should not be required to work;
            # at minimum new refresh must succeed (asserted above).
            _ = refresh
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
