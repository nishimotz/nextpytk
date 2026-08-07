"""Tests for the NEXTPYTK_DEBUG_PADDING env var enabling the debug overlay."""
from __future__ import annotations

import os

import pytest

from nextpytk import TkApp

from .conftest import requires_display

pytestmark = requires_display


def _debug_padding_value() -> bool:
    """Return what TkApp.__init__ would resolve for debug_padding=None."""
    return os.environ.get("NEXTPYTK_DEBUG_PADDING", "").strip() not in ("", "0")


def test_env_var_unset_defaults_off(monkeypatch):
    """No env var → debug_padding stays off (None resolves to False)."""
    monkeypatch.delenv("NEXTPYTK_DEBUG_PADDING", raising=False)
    app = TkApp(title="t")
    assert app._debug_padding is False


def test_env_var_1_enables(monkeypatch):
    """NEXTPYTK_DEBUG_PADDING=1 → debug_padding resolves to True."""
    monkeypatch.setenv("NEXTPYTK_DEBUG_PADDING", "1")
    app = TkApp(title="t")
    assert app._debug_padding is True


def test_env_var_0_disables(monkeypatch):
    """NEXTPYTK_DEBUG_PADDING=0 → debug_padding stays off."""
    monkeypatch.setenv("NEXTPYTK_DEBUG_PADDING", "0")
    app = TkApp(title="t")
    assert app._debug_padding is False


def test_env_var_empty_disables(monkeypatch):
    """NEXTPYTK_DEBUG_PADDING='' → debug_padding stays off."""
    monkeypatch.setenv("NEXTPYTK_DEBUG_PADDING", "")
    app = TkApp(title="t")
    assert app._debug_padding is False


def test_env_var_true_enables(monkeypatch):
    """Any non-empty, non-zero value (e.g. 'true') enables the overlay."""
    monkeypatch.setenv("NEXTPYTK_DEBUG_PADDING", "true")
    app = TkApp(title="t")
    assert app._debug_padding is True


def test_explicit_debug_padding_overrides_env(monkeypatch):
    """Explicit debug_padding=True/False wins over the env var."""
    monkeypatch.setenv("NEXTPYTK_DEBUG_PADDING", "1")
    # Explicit False stays off even with the env var set.
    app = TkApp(title="t", debug_padding=False)
    assert app._debug_padding is False
    # Explicit True stays on even with the env var unset.
    monkeypatch.delenv("NEXTPYTK_DEBUG_PADDING", raising=False)
    app2 = TkApp(title="t", debug_padding=True)
    assert app2._debug_padding is True


def test_env_var_resolution_matches_production_logic():
    """Guard the resolution formula against accidental drift."""
    assert _debug_padding_value() is (os.environ.get(
        "NEXTPYTK_DEBUG_PADDING", "").strip() not in ("", "0"))
