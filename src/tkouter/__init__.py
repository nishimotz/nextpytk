"""tkouter: Flask-inspired decorator API on tkinter with DI layout and typed options."""

from tkouter.app import TkApp
from tkouter.layout import Layout, LayoutBuilder
from tkouter import types
from tkouter.widgets import WidgetSpec

__all__ = ["TkApp", "Layout", "LayoutBuilder", "WidgetSpec", "types"]
