"""Event handlers mixin for dispatching widget events into state transitions."""

from __future__ import annotations

import sys
import tkinter as tk
from typing import TYPE_CHECKING, Any

from nextpytk.types import EntryEventHandler, ListboxEventHandler, ListboxSelectCallback
from nextpytk.widgets import WidgetSpec


class EventHandlersMixin:
    """Provides callback and event handlers that convert GUI events to state updates."""

    _tk_widgets: dict[str, tk.Widget]
    _treeview_inner: dict[str, Any]
    _text_inner: dict[str, tk.Text]

    @property
    def _state(self) -> dict[str, Any]:
        raise NotImplementedError

    def _entry_values_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def _entry_effective_value(self, name: str) -> str:
        raise NotImplementedError

    def _dispatch(self, spec_name: str, fn: Any, *args: Any) -> Any:
        raise NotImplementedError

    def _apply_state(self, update: dict[str, Any]) -> None:
        raise NotImplementedError

    def _apply_state_dict(self, update: dict[str, Any], *, full: bool) -> None:
        raise NotImplementedError

    def _treeview_selected_index(self, spec: WidgetSpec) -> int:
        raise NotImplementedError

    def _apply_callback_result(self, result: Any) -> None:
        if isinstance(result, dict):
            self._apply_state(result)

    def _warn_invalid_callback_return(self, spec_name: str, result: Any) -> None:
        """Warn when a callback returns a value the framework cannot use."""
        expected = f'{{"{spec_name}": value}}'
        if isinstance(result, set):
            print(
                f"nextpytk: callback for {spec_name!r} returned a set "
                f"{result!r}; expected a state dict like {expected!r} or a "
                f"plain string. Update ignored.",
                file=sys.stderr,
            )
        elif isinstance(result, (list, tuple)):
            print(
                f"nextpytk: callback for {spec_name!r} returned a "
                f"{type(result).__name__} {result!r}; expected a state dict or "
                f"a plain string. Widget order is declared via layout=, not "
                f"the callback return. Update ignored.",
                file=sys.stderr,
            )
        elif isinstance(result, str):
            print(
                f"nextpytk: callback for {spec_name!r} returned the string "
                f"{result!r}; expected a state dict. (A plain string updates "
                f"the label only for button callbacks.) Update ignored.",
                file=sys.stderr,
            )

    def _on_button_click(self, spec: WidgetSpec, fn: Any) -> None:
        values = self._entry_values_dict()
        result = self._dispatch(spec.name, fn, values)
        if isinstance(result, str):
            result = {spec.name: result}
        elif isinstance(result, (set, list, tuple)):
            self._warn_invalid_callback_return(spec.name, result)
            result = None
        self._apply_callback_result(result)

    def _on_entry_change(self, spec: WidgetSpec, fn: Any) -> None:
        value = self._entry_effective_value(spec.name)
        result = self._dispatch(spec.name, fn, value)
        if isinstance(result, (str, set, list, tuple)):
            self._warn_invalid_callback_return(spec.name, result)
            result = None
        self._apply_callback_result(result)

    def _on_entry_event(self, handler: EntryEventHandler) -> None:
        """Invoke a widget-level entry event handler and apply its state update."""
        values = self._entry_values_dict()
        result = self._dispatch("entry_event", handler, values)
        if isinstance(result, dict) and result:
            self._apply_state(result)

    def _on_listbox_event(self, handler: ListboxEventHandler) -> None:
        """Invoke a widget-level listbox event handler."""
        result = self._dispatch("listbox_event", handler, dict(self._state))
        if isinstance(result, dict) and result:
            self._apply_state(result)

    def _on_bind_trigger(self, spec: WidgetSpec, fn: Any) -> None:
        result = self._dispatch(spec.name, fn, dict(self._state))
        if isinstance(result, dict) and result:
            self._apply_state(result)

    def _on_checkbutton_change(self, spec: WidgetSpec, fn: Any,
                                var: tk.StringVar, key: str) -> None:
        val = var.get()
        self._state[key] = val
        self._apply_callback_result(self._dispatch(spec.name, fn, val == "1"))

    def _on_radiobutton_change(self, spec: WidgetSpec, fn: Any,
                                var: tk.Variable, key: str) -> None:
        val = var.get()
        self._state[key] = val
        self._apply_callback_result(self._dispatch(spec.name, fn, val))

    def _on_var_change(self, spec: WidgetSpec, fn: Any,
                        var: tk.Variable, key: str) -> None:
        val = var.get()
        self._state[key] = val
        self._apply_callback_result(self._dispatch(spec.name, fn, val))

    def _on_scale_change(self, spec: WidgetSpec, value: str) -> None:
        key = spec.extras.get("state_key", spec.name)
        val = int(float(value))
        self._state[key] = val
        if spec.on_update is not None:
            self._apply_callback_result(self._dispatch(spec.name, spec.on_update, val))

    def _on_spinbox_change(self, spec: WidgetSpec) -> None:
        key = spec.extras.get("state_key", spec.name)
        val = str(self._state.get(key, ""))
        if spec.on_update is not None:
            self._apply_callback_result(self._dispatch(spec.name, spec.on_update, val))

    def _on_combobox_change(self, spec: WidgetSpec) -> None:
        key = spec.extras.get("state_key", spec.name)
        w = self._tk_widgets.get(spec.name)
        val = ""
        if w is not None and hasattr(w, "get"):
            val = str(getattr(w, "get")())
        self._state[key] = val
        if spec.on_update is not None:
            self._apply_callback_result(self._dispatch(spec.name, spec.on_update, val))

    def _on_text_change(self, spec: WidgetSpec, fn: Any) -> None:
        w = self._text_inner.get(spec.name)
        value = ""
        if w is not None and hasattr(w, "get"):
            value = w.get("1.0", "end-1c")
        self._apply_callback_result(self._dispatch(spec.name, fn, value))

    def _on_listbox_select(self, spec: WidgetSpec, fn: Any) -> None:
        w = self._tk_widgets.get(spec.name)
        if w is None:
            w = self._tk_widgets.get(f"_inner_{spec.name}")
        idx = -1
        if w is not None and hasattr(w, "curselection"):
            sel = getattr(w, "curselection")()
            if sel:
                idx = int(sel[0])
        self._state[spec.name] = idx
        self._apply_callback_result(self._dispatch(spec.name, fn, idx))

    def _apply_treeview_select(self, spec: WidgetSpec, fn: Any, idx: int) -> None:
        """Apply treeview row selection (index) and refresh dependent widgets."""
        if self._state.get(spec.name) == idx:
            return
        self._state[spec.name] = idx
        result = self._dispatch(spec.name, fn, idx)
        if isinstance(result, dict):
            self._apply_state_dict(result, full=False)

    def _on_treeview_select(self, spec: WidgetSpec, fn: Any) -> None:
        idx = self._treeview_selected_index(spec)
        self._apply_treeview_select(spec, fn, idx)

    def _on_treeview_click(self, spec: WidgetSpec, fn: Any, event: tk.Event[tk.Misc]) -> None:
        """Handle row click via coordinates (reliable when ``<<TreeviewSelect>>`` is flaky)."""
        tree = self._treeview_inner.get(spec.name)
        if tree is None:
            return
        region = tree.identify_region(event.x, event.y)
        if region not in ("cell", "tree"):
            return
        iid = tree.identify_row(event.y)
        if not iid:
            return
        idx = int(tree.index(iid))
        if tree.selection() != (iid,):
            tree.selection_set(iid)
            tree.focus(iid)
        self._apply_treeview_select(spec, fn, idx)

    def _on_treeview_activate(
        self, spec: WidgetSpec, fn: Any, event: tk.Event[tk.Misc] | None = None
    ) -> None:
        idx = self._treeview_selected_index(spec)
        if idx < 0:
            return
        result = self._dispatch(spec.name, fn, idx)
        if isinstance(result, dict):
            self._state[spec.name] = idx
            self._apply_state_dict(result, full=False)
