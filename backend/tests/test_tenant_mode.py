"""Normalize and accept tenant_mode values."""

from app.infrastructure.system_overrides import normalize_tenant_mode


def test_normalize_tenant_mode() -> None:
    assert normalize_tenant_mode("single") == "single"
    assert normalize_tenant_mode("MULTI") == "multi"
    assert normalize_tenant_mode(None) == "single"
    assert normalize_tenant_mode("weird") == "single"
