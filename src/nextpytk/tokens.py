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

import tkinter.font as tkfont

# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------

# Palette: nextpytk design system.
# Warm neutral ground with brown interaction accent.
# Contrast pairs are regression-tested in tests/test_tokens.py
# (WCAG 1.4.3 Contrast (Minimum), 1.4.11 Non-text Contrast).
BG = "#faf8f4"            # Background (page ground)
SURFACE = "#f1eae0"       # Surface (fields, panels)
CARD = "#ffffff"          # Card background (design uses pure white on BG)
TEXT = "#302b24"          # Text Primary
TEXT_SECONDARY = "#4a4339"  # Paragraph text on cards/sections
ACCENT = "#7a5a34"        # Accent Text: links, interaction (AA on BG/CARD)
ON_ACCENT = "#ffffff"     # Text on ACCENT surfaces (primary buttons)
DIVIDER = "#e3d9c8"       # Border: rules and card borders
FOCUS = "#21201c"         # Focus Ring (3px; WCAG 2.4.7 Focus Visible)
ACCENT_BADGE = "#efc53e"  # Accent Moon: badge/highlight, decorative use only
ACCENT_BADGE_TEXT = "#3d2f0a"  # Text on ACCENT_BADGE
SELECTION_BG = "#e8b93a"  # ::selection background
SELECTION_FG = "#21201c"  # ::selection text

# Neutral tonal ramp -- --color-neutral-100..900 (warm)
NEUTRAL = {
    100: "#f7f3ec", 200: "#f1eae0", 300: "#e3d9c8", 400: "#c4b7a3",
    500: "#9c8f7c", 600: "#6e655a", 700: "#544c41", 800: "#3d2f20", 900: "#302b24",
}

# Accent tonal ramp (400 = Accent Tan: decorative only, not for borders/text —
# 2.65:1 on white. 500 = ACCENT. 600/700 = hover / link-hover)
ACCENT_RAMP = {
    100: "#f5efe6", 200: "#eadfcd", 300: "#d6c3a5", 400: "#b99a72",
    500: "#7a5a34", 600: "#5f4527", 700: "#513d24", 800: "#43301a", 900: "#332413",
}

ACCENT_HOVER = ACCENT_RAMP[600]
ACCENT_PRESSED = ACCENT_RAMP[700]
TEXT_MUTED = NEUTRAL[600]
DISABLED_OPACITY = 0.45

# Backwards-compatible placeholder color used by nextpytk entry hints.
PLACEHOLDER_FG = TEXT_MUTED

# ---------------------------------------------------------------------------
# Spacing -- 4px base unit. Use these for every pad/gap; never a bare integer.
# ---------------------------------------------------------------------------

SPACE = {1: 4, 2: 8, 3: 12, 4: 16, 6: 24, 8: 32}

# Minimum interactive target size (buttons and links must be at least 44px).
# Regression-tested in tests/test_target_size.py (WCAG 2.5.5 Target Size).
MIN_TARGET = 44

# ---------------------------------------------------------------------------
# Radius -- the web spec uses 8px (buttons) / 14px (cards), but ttk's clam
# theme cannot render rounded corners; Tk stays square. Kept for schema
# parity and future custom widgets.
# ---------------------------------------------------------------------------

RADIUS = 0

# ---------------------------------------------------------------------------
# Widget defaults -- shared by builders when the app does not override.
# ---------------------------------------------------------------------------

DEFAULT_LISTBOX_ROWS = 18
DEFAULT_COMBOBOX_WIDTH = 24  # character columns, matches Entry default feel

# ---------------------------------------------------------------------------
# Type -- Japanese Noto Sans JP / Latin Work Sans, with system fallbacks.
# ---------------------------------------------------------------------------

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
    """Re-resolve the preferred font family after Tk has initialized fonts.

    When nextpytk is imported before ``tk.Tk()`` has run (common in tests
    and when modules are imported at interpreter startup), ``tkfont.families()``
    may be empty and ``FONT_FAMILY`` falls back to ``TkDefaultFont``.  Call this
    before applying the theme to pick the best installed UI font.
    """
    global FONT_FAMILY
    FONT_FAMILY = _resolve_font_family()
    return FONT_FAMILY
FONT_WEIGHT_HEADING = "bold"

# Type scale -- pixel sizes (Tk negative size = px):
# Display 44/700, H1 32/700, H2 24/600, H3 19/600, Body 16/400, Small 14/400.
# h5 = button size (15/600).
TYPE_SCALE = {
    "display": -44,
    "h1": -32,
    "h2": -24,
    "h3": -19,
    "h4": -16,
    "h5": -15,
    "h6": -13,
    "body": -16,
    "small": -14,
}


def font(scale="body", weight=None, family=None):
    """Return a (family, size, weight) font tuple for the given type-scale step."""
    fam = family or FONT_FAMILY
    size = TYPE_SCALE.get(scale, TYPE_SCALE["body"])
    w = weight or (FONT_WEIGHT_HEADING if scale in ("h1", "h2", "h3", "h4") else "normal")
    return (fam, size, w) if w and w != "normal" else (fam, size)
