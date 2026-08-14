# -*- coding: utf-8 -*-
"""
Kizashi design tokens for Tkinter/ttk applications.

Flat, warm-neutral ground with a brown accent, zero corner radius, strong
2px rules, and a modular spacing/type scale. Every value below traces back
to a CSS custom property of the same name -- change the look here, once,
and every app built on this module follows.

Do not hard-code a color, font, or spacing number in application code:
import from here instead.
"""

from dataclasses import dataclass, field
from typing import Any
import tkinter.font as tkfont

# ---------------------------------------------------------------------------
# ThemeTokens dataclass & Built-in Themes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThemeTokens:
    """Design tokens defining colors, typography, and spacing for a theme."""

    name: str = "kizashi"
    bg: str = "#faf8f4"
    surface: str = "#f1ece3"
    card: str = "#ffffff"
    text: str = "#302b24"
    text_secondary: str = "#4a4339"
    text_muted: str = "#6e655a"
    accent: str = "#7a5a34"
    on_accent: str = "#ffffff"
    accent_hover: str = "#5f4527"
    accent_pressed: str = "#513d24"
    divider: str = "#e3d9c8"
    focus: str = "#21201c"
    accent_badge: str = "#efc53e"
    accent_badge_text: str = "#3d2f0a"
    selection_bg: str = "#e8b93a"
    selection_fg: str = "#21201c"
    neutral: dict[int, str] = field(default_factory=lambda: {
        100: "#f7f3ec", 200: "#f1eae0", 300: "#e3d9c8", 400: "#c4b7a3",
        500: "#9c8f7c", 600: "#6e655a", 700: "#544c41", 800: "#3d2f20", 900: "#302b24",
    })
    accent_ramp: dict[int, str] = field(default_factory=lambda: {
        100: "#f5efe6", 200: "#eadfcd", 300: "#d6c3a5", 400: "#b99a72",
        500: "#7a5a34", 600: "#5f4527", 700: "#513d24", 800: "#43301a", 900: "#332413",
    })
    space: dict[int, int] = field(default_factory=lambda: {1: 4, 2: 8, 3: 12, 4: 16, 6: 24, 8: 32})
    min_target: int = 44
    radius: int = 0
    font_family: str = "TkDefaultFont"
    type_scale: dict[str, int] = field(default_factory=lambda: {
        "display": -44, "h1": -32, "h2": -24, "h3": -19,
        "h4": -16, "h5": -15, "h6": -13, "body": -16, "small": -14,
    })

    def font(self, scale: str = "body", weight: str | None = None, family: str | None = None) -> tuple[Any, ...]:
        fam = family or (self.font_family if self.font_family != "TkDefaultFont" else FONT_FAMILY)
        size = self.type_scale.get(scale, self.type_scale.get("body", -16))
        w = weight or ("bold" if scale in ("h1", "h2", "h3", "h4") else "normal")
        return (fam, size, w) if w and w != "normal" else (fam, size)


KIZASHI_LIGHT = ThemeTokens(name="kizashi")

KIZASHI_DARK = ThemeTokens(
    name="kizashi-dark",
    bg="#1e1e1e",
    surface="#282828",
    card="#2d2d2d",
    text="#f0ebe4",
    text_secondary="#c4b7a3",
    text_muted="#9c8f7c",
    accent="#d4a373",
    on_accent="#1e1e1e",
    accent_hover="#e2be9b",
    accent_pressed="#b98858",
    divider="#3d3830",
    focus="#efc53e",
    accent_badge="#544c41",
    accent_badge_text="#f7f3ec",
    selection_bg="#5f4527",
    selection_fg="#ffffff",
    neutral={
        100: "#302b24", 200: "#3d2f20", 300: "#544c41", 400: "#6e655a",
        500: "#9c8f7c", 600: "#c4b7a3", 700: "#e3d9c8", 800: "#f1eae0", 900: "#f7f3ec",
    },
    accent_ramp={
        100: "#332413", 200: "#43301a", 300: "#513d24", 400: "#5f4527",
        500: "#7a5a34", 600: "#b99a72", 700: "#d6c3a5", 800: "#eadfcd", 900: "#f5efe6",
    },
)

# ---------------------------------------------------------------------------
# Backward-compatible module-level constants (Kizashi Light)
# ---------------------------------------------------------------------------

BG = KIZASHI_LIGHT.bg
SURFACE = KIZASHI_LIGHT.surface
CARD = KIZASHI_LIGHT.card
TEXT = KIZASHI_LIGHT.text
TEXT_SECONDARY = KIZASHI_LIGHT.text_secondary
ACCENT = KIZASHI_LIGHT.accent
ON_ACCENT = KIZASHI_LIGHT.on_accent
DIVIDER = KIZASHI_LIGHT.divider
FOCUS = KIZASHI_LIGHT.focus
ACCENT_BADGE = KIZASHI_LIGHT.accent_badge
ACCENT_BADGE_TEXT = KIZASHI_LIGHT.accent_badge_text
SELECTION_BG = KIZASHI_LIGHT.selection_bg
SELECTION_FG = KIZASHI_LIGHT.selection_fg
NEUTRAL = KIZASHI_LIGHT.neutral
ACCENT_RAMP = KIZASHI_LIGHT.accent_ramp
ACCENT_HOVER = KIZASHI_LIGHT.accent_hover
ACCENT_PRESSED = KIZASHI_LIGHT.accent_pressed
TEXT_MUTED = KIZASHI_LIGHT.text_muted
DISABLED_OPACITY = 0.45
PLACEHOLDER_FG = TEXT_MUTED

SPACE = KIZASHI_LIGHT.space
MIN_TARGET = KIZASHI_LIGHT.min_target
RADIUS = KIZASHI_LIGHT.radius
DEFAULT_LISTBOX_ROWS = 18
DEFAULT_COMBOBOX_WIDTH = 24

_FALLBACKS = ["Noto Sans JP", "Work Sans", "Hiragino Sans", "Yu Gothic UI",
              "Segoe UI", "Helvetica Neue", "DejaVu Sans"]


def _resolve_font_family():
    try:
        available = set(tkfont.families())
    except Exception:
        return "TkDefaultFont"
    for name in _FALLBACKS:
        if name in available:
            return name
    return "TkDefaultFont"


FONT_FAMILY = _resolve_font_family()


def resolve_font_family():
    """Re-resolve the preferred font family after Tk has initialized fonts."""
    global FONT_FAMILY
    FONT_FAMILY = _resolve_font_family()
    return FONT_FAMILY


FONT_WEIGHT_HEADING = "bold"
TYPE_SCALE = KIZASHI_LIGHT.type_scale


def font(scale="body", weight=None, family=None):
    """Return a (family, size, weight) font tuple for the given type-scale step."""
    fam = family or FONT_FAMILY
    size = TYPE_SCALE.get(scale, TYPE_SCALE["body"])
    w = weight or (FONT_WEIGHT_HEADING if scale in ("h1", "h2", "h3", "h4") else "normal")
    return (fam, size, w) if w and w != "normal" else (fam, size)
