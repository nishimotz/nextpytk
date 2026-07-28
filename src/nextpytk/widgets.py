"""Widget metadata for nextpytk: pure schema, no tkinter references."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WidgetSpec:
    """Schema for one named widget slot. Pure data: no tkinter references.

    This is the key insight of nextpytk: the Python-side representation of a
    widget is nothing but a schema entry + callback. The actual GUI object
    lives in tkinter. Python doesn't need to own it.
    """

    name: str

    # Widget kind: label | status | message | button | entry | checkbutton
    #              | radiobutton | text | scale | spinbox | combobox | listbox
    #              | treeview | paned | progressbar | canvas | bind | menubar
    #              | filepicker
    kind: str

    # Common label / display text
    label_text: str = ""

    # Entry-specific
    placeholder: str = ""
    placeholder_as_hint: bool = True

    # A11y
    role: str | None = None
    description: str | None = None

    # Callbacks
    on_update: Callable[..., Any] | None = None
    on_click: Callable[..., Any] | None = None

    # Buttons: conditional disable
    enabled_if: Callable[[dict[str, Any]], bool] | None = None

    # Key bindings: list of (sequence, label) tuples
    # e.g. [("<Control-s>", "Ctrl+S"), ("<Alt-Down>", "Alt+Down")]
    bindings: list[tuple[str, str]] = field(default_factory=list)

    # Extra widget-type-specific parameters (checkbutton values, listbox items,
    # spinbox range, scale range, text dimensions, takefocus for Tab order, etc.)
    extras: dict[str, Any] = field(default_factory=dict)