"""nextpytk: Flask-inspired decorator API on tkinter with DI layout and typed options."""

from nextpytk.app import TkApp
from nextpytk.layout import Layout, LayoutBuilder
from nextpytk import types
from nextpytk.widgets import WidgetSpec

__all__ = ["TkApp", "Layout", "LayoutBuilder", "WidgetSpec", "types"]
