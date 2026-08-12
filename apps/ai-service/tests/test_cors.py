from __future__ import annotations

from types import SimpleNamespace

from examshield_ai.server import resolve_cors_headers


def _settings(cors_origin: str) -> SimpleNamespace:
    return SimpleNamespace(cors_origin=cors_origin)


def test_default_config_no_longer_returns_wildcard():
    """§2.5: the default must not be a permissive `*`. With an empty allow-list,
    no Access-Control-Allow-Origin header should be emitted for any origin."""
    headers = resolve_cors_headers(_settings(""), "https://evil.example.com")
    assert "Access-Control-Allow-Origin" not in headers


def test_matching_origin_is_reflected_with_vary_header():
    settings = _settings("https://app.vercel.app")
    headers = resolve_cors_headers(settings, "https://app.vercel.app")
    assert headers["Access-Control-Allow-Origin"] == "https://app.vercel.app"
    assert headers["Vary"] == "Origin"


def test_non_matching_origin_is_rejected():
    settings = _settings("https://app.vercel.app")
    headers = resolve_cors_headers(settings, "https://evil.example.com")
    assert "Access-Control-Allow-Origin" not in headers


def test_multiple_allowed_origins_supported():
    settings = _settings("https://a.vercel.app, https://b.vercel.app")
    assert resolve_cors_headers(settings, "https://a.vercel.app")["Access-Control-Allow-Origin"] == "https://a.vercel.app"
    assert resolve_cors_headers(settings, "https://b.vercel.app")["Access-Control-Allow-Origin"] == "https://b.vercel.app"


def test_explicit_wildcard_still_allows_all_for_backward_compat():
    headers = resolve_cors_headers(_settings("*"), "https://anything.example.com")
    assert headers["Access-Control-Allow-Origin"] == "https://anything.example.com"


def test_missing_origin_header_emits_no_cors():
    headers = resolve_cors_headers(_settings("https://app.vercel.app"), None)
    assert "Access-Control-Allow-Origin" not in headers
