from __future__ import annotations

from examshield_ai.cors import allowed_cors_origins


def test_default_config_is_fail_closed():
    assert allowed_cors_origins("") == []


def test_single_allowed_origin():
    assert allowed_cors_origins("https://app.vercel.app") == ["https://app.vercel.app"]


def test_comma_separated_origins_are_trimmed():
    assert allowed_cors_origins("https://a.vercel.app, https://b.vercel.app") == [
        "https://a.vercel.app",
        "https://b.vercel.app",
    ]


def test_explicit_wildcard_still_allows_all_for_backward_compat():
    assert allowed_cors_origins("*") == ["*"]


def test_wildcard_wins_over_other_entries():
    assert allowed_cors_origins("https://app.vercel.app, *") == ["*"]


def test_whitespace_only_is_treated_as_empty():
    assert allowed_cors_origins("   ") == []
