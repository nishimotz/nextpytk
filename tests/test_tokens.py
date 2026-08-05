"""Design-token contrast regressions (WCAG 1.4.3, 1.4.11).

Every color pair nextpytk uses by default must meet its WCAG ratio:
4.5:1 for text (1.4.3 Contrast Minimum), 3:1 for UI boundaries and
focus rings (1.4.11 Non-text Contrast). Swap the palette in tokens.py
and these tests re-verify it.
"""

from __future__ import annotations

import pytest

from nextpytk import tokens as t


def _linear(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# (foreground, background, required ratio, where it is used)
TEXT_PAIRS = [
    (t.TEXT, t.BG, 4.5, "body text on window ground"),
    (t.TEXT, t.SURFACE, 4.5, "text in fields/panels"),
    (t.TEXT, t.CARD, 4.5, "text on white cards"),
    (t.TEXT_SECONDARY, t.BG, 4.5, "paragraph text on ground"),
    (t.TEXT_SECONDARY, t.CARD, 4.5, "paragraph text on cards"),
    (t.TEXT_MUTED, t.BG, 4.5, "muted text on ground"),
    (t.TEXT_MUTED, t.SURFACE, 4.5, "placeholder in entries (PLACEHOLDER_FG)"),
    (t.TEXT_MUTED, t.CARD, 4.5, "muted text on cards"),
    (t.ACCENT, t.BG, 4.5, "links / accent text on ground"),
    (t.ACCENT, t.CARD, 4.5, "links / accent text on cards"),
    (t.ON_ACCENT, t.ACCENT, 4.5, "Primary button label on accent"),
    (t.ACCENT_RAMP[700], t.ACCENT_RAMP[100], 4.5, "selected tab / treeview row"),
    (t.ACCENT_BADGE_TEXT, t.ACCENT_BADGE, 4.5, "badge text on Accent Moon"),
    (t.SELECTION_FG, t.SELECTION_BG, 4.5, "text selection"),
]

UI_PAIRS = [
    (t.ACCENT, t.BG, 3.0, "accent as interactive boundary"),
    (t.FOCUS, t.BG, 3.0, "focus ring on ground"),
    (t.FOCUS, t.SURFACE, 3.0, "focus ring on fields"),
    # Scale thumb: BG fill on an ACCENT border, sitting on the SURFACE
    # trough. The ACCENT border gives the non-text contrast needed to pick the
    # thumb out of the trough (WCAG 1.4.11); the BG fill stays legible
    # against the border so the thumb reads as a single control.
    (t.ACCENT, t.SURFACE, 3.0, "scale thumb border on trough"),
    (t.BG, t.ACCENT, 3.0, "scale thumb fill on its border"),
    # Hover/pressed border states stay visible on the trough too.
    (t.ACCENT_HOVER, t.SURFACE, 3.0, "scale thumb border hover on trough"),
    (t.ACCENT_PRESSED, t.SURFACE, 3.0, "scale thumb border pressed on trough"),
    # Scrollbar thumb shares the scale thumb palette: BG fill, ACCENT border
    # on the SURFACE trough, so it stays visible the same way.
    (t.ACCENT, t.SURFACE, 3.0, "scrollbar thumb border on trough"),
    (t.BG, t.ACCENT, 3.0, "scrollbar thumb fill on its border"),
    (t.ACCENT_HOVER, t.SURFACE, 3.0, "scrollbar thumb border hover on trough"),
    (t.ACCENT_PRESSED, t.SURFACE, 3.0, "scrollbar thumb border pressed on trough"),
]


@pytest.mark.parametrize("fg,bg,minimum,label", TEXT_PAIRS + UI_PAIRS,
                         ids=[p[3] for p in TEXT_PAIRS + UI_PAIRS])
def test_default_color_pair_meets_contrast(fg, bg, minimum, label):
    ratio = contrast(fg, bg)
    assert ratio >= minimum, (
        f"{label}: contrast {ratio:.2f}:1 < required {minimum}:1 ({fg} on {bg})"
    )


def test_hover_pressed_keep_button_label_readable():
    for state_color in (t.ACCENT_HOVER, t.ACCENT_PRESSED):
        assert contrast(t.ON_ACCENT, state_color) >= 4.5
