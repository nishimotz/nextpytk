"""JSON Schema exporter for nextpytk application structure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from nextpytk.widgets import WidgetSpec


class SchemaExporter:
    """Exports registered widgets and current application state to JSON-compatible dict."""

    @staticmethod
    def export(
        title: str,
        widgets: list[WidgetSpec],
        state: dict[str, Any],
        combobox_values_fn: Callable[[WidgetSpec], list[str]],
        listbox_items_fn: Callable[[WidgetSpec], list[str]],
    ) -> dict[str, Any]:
        widgets_out: list[dict[str, Any]] = []
        for w in widgets:
            d: dict[str, Any] = {
                "name": w.name,
                "kind": w.kind,
                "label": w.label_text,
                "role": w.role,
                "description": w.description,
            }
            if w.kind in ("checkbutton", "scale", "spinbox", "combobox"):
                d["state_key"] = w.extras.get("state_key")
            if w.kind == "combobox":
                d["values_key"] = w.extras.get("values_key")
                values = combobox_values_fn(w)
                d["values"] = values
                d["readonly"] = w.extras.get("readonly", False)
            if w.kind == "radiobutton":
                d["group_key"] = w.extras.get("group_key")
                d["rb_value"] = w.extras.get("rb_value")
            if w.kind == "listbox":
                d["items_key"] = w.extras.get("items_key")
                items = listbox_items_fn(w)
                d["items_count"] = len(items)
            if w.kind == "treeview":
                d["columns"] = w.extras.get("column_ids", [])
                d["rows_key"] = w.extras.get("rows_key")
                d["rows_count"] = len(state.get(
                    w.extras.get("rows_key", f"{w.name}_rows"), []
                ))
            if w.kind == "paned":
                d["panes"] = list(w.extras.get("panes", ()))
                d["orient"] = w.extras.get("orient", "horizontal")
                d["weights"] = w.extras.get("weights", [])
            if w.kind == "progressbar":
                d["state_key"] = w.extras.get("state_key")
                d["maximum"] = w.extras.get("maximum", 100)
                d["mode"] = w.extras.get("mode", "determinate")
                sk = w.extras.get("state_key", w.name)
                d["value"] = state.get(sk, 0)
            if w.kind == "entry":
                d["placeholder_as_hint"] = w.placeholder_as_hint
            if w.kind == "filepicker":
                d["mode"] = w.extras.get("mode", "open")
                for opt in ("title", "initialdir", "initialfile", "filetypes", "defaultextension"):
                    if opt in w.extras:
                        d[opt] = w.extras[opt]
            if w.kind == "menubar":
                d["items"] = [
                    {"label": i.get("label"), "command": i.get("command"),
                     "items": i.get("items")}
                    for i in w.extras.get("items", [])
                    if not i.get("separator")
                ]
            if "takefocus" in w.extras:
                d["takefocus"] = w.extras["takefocus"]
            widgets_out.append(d)
        return {"title": title, "widgets": widgets_out}
