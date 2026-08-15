"""Accessibility engine for nextpytk supporting Tk 9.1+ / TIP 733."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nextpytk.widgets import WidgetSpec


class A11yEngine:
    """Encapsulates accessibility calls and state transitions for Tk widgets."""

    def __init__(self) -> None:
        self.acc_supported: bool | None = None
        self.last_toggles: dict[str, str] = {}

    def call_accessible(self, root: tk.Misc | None, *args: str) -> bool:
        """Call ``tk accessible ...``, returning True on success.

        On the first ``TclError`` (Tk < 9.1) sets ``acc_supported = False``
        so all subsequent calls short-circuit without touching the Tcl
        interpreter.
        """
        if root is None or self.acc_supported is False:
            return False
        try:
            root.tk.call("tk", "accessible", *args)
            self.acc_supported = True
            return True
        except tk.TclError:
            if self.acc_supported is None:
                self.acc_supported = False
            return False

    def apply_a11y(self, root: tk.Misc | None, target: tk.Widget | None, spec: WidgetSpec) -> None:
        """Route ``WidgetSpec.role`` / ``description`` to Tk accessible attrs."""
        if target is None:
            return
        if spec.role:
            self.call_accessible(root, "set_acc_role", str(target), spec.role)
        if spec.description:
            self.call_accessible(root, "set_acc_description", str(target), spec.description)

    def apply_to_layout_frames(self, root: tk.Misc | None, frames: Iterable[tk.Misc]) -> None:
        """Mark intermediate layout frames as grouping containers."""
        seen: set[int] = set()
        for frame in frames:
            fid = id(frame)
            if fid in seen:
                continue
            seen.add(fid)
            if not self.call_accessible(root, "set_acc_role", str(frame), "Grouping"):
                return

    def emit_selection_change(self, root: tk.Misc | None, target: tk.Widget | None) -> None:
        """Notify AT that the selection of target has changed."""
        if target is None:
            return
        self.call_accessible(root, "emit_selection_change", str(target))

    def emit_value_change(
        self,
        root: tk.Misc | None,
        target: tk.Widget | None,
        value: str,
    ) -> None:
        """Notify AT that the value of target has changed."""
        if target is None:
            return
        self.call_accessible(root, "set_acc_value", str(target), value)

    def emit_state_change(
        self,
        root: tk.Misc | None,
        target: tk.Widget | None,
        spec: WidgetSpec,
        value: str,
        state_key: str,
    ) -> None:
        """Notify AT that the checked/selected state of spec has changed."""
        if target is None:
            return
        cache_key = f"{spec.kind}:{spec.name}:{state_key}"
        if self.last_toggles.get(cache_key) == value:
            return
        self.last_toggles[cache_key] = value
        self.call_accessible(root, "set_acc_value", str(target), value)
