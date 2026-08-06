"""Appearance / branding helper checks."""

from app.api.v1.i18n import _HEX_COLOR


def test_hex_color_accepts_rrggbb() -> None:
    assert _HEX_COLOR.match("#0B3D5C")
    assert _HEX_COLOR.match("#abcdef")


def test_hex_color_rejects_invalid() -> None:
    assert _HEX_COLOR.match("0B3D5C") is None
    assert _HEX_COLOR.match("#fff") is None
    assert _HEX_COLOR.match("#GGGGGG") is None
    assert _HEX_COLOR.match("") is None
