"""nextpytk: accessible, declarative Tkinter apps from ordinary Python functions."""

import importlib.metadata

from nextpytk.app import TkApp
from nextpytk.layout import Layout, LayoutBuilder
from nextpytk import types
from nextpytk.widgets import WidgetSpec
from nextpytk.theme import (
    apply_theme,
    configure_window,
    content_frame,
    divider,
    heading,
    field_row,
    window_header,
    data_list,
    add_row,
    clear_rows,
    status_bar,
    button,
)
from nextpytk import tokens

try:
    __version__ = importlib.metadata.version("nextpytk")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover - editable fallback
    __version__ = "0.0.0+unknown"

__all__ = [
    "TkApp",
    "Layout",
    "LayoutBuilder",
    "WidgetSpec",
    "types",
    "apply_theme",
    "configure_window",
    "content_frame",
    "divider",
    "heading",
    "field_row",
    "window_header",
    "data_list",
    "add_row",
    "clear_rows",
    "status_bar",
    "button",
    "tokens",
    "__version__",
]
