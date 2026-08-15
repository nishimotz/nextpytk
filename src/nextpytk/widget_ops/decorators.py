"""Widget registration decorators and direct addition methods (DSL layer)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from nextpytk import tokens as t
from nextpytk.types import (
    CanvasOptions,
    CheckbuttonOptions,
    ComboboxOptions,
    EntryOptions,
    FilepickerCallback,
    FilepickerOptions,
    LabelOptions,
    ListboxOptions,
    ListboxSelectCallback,
    MenubarCallback,
    MenubarOptions,
    MessageOptions,
    PanedOptions,
    ProgressbarOptions,
    RadiobuttonOptions,
    ScaleOptions,
    SpinboxOptions,
    TextOptions,
    TreeviewOptions,
    Unpack,
)
from nextpytk.widgets import WidgetSpec

LabelCallback = Callable[[], str | dict[str, Any]]
ButtonCallback = (
    Callable[[dict[str, Any]], dict[str, Any]]
    | Callable[[], dict[str, Any]]
)
BindCallback = ButtonCallback
ValueCallback = Callable[[str], dict[str, Any]] | Callable[[], dict[str, Any]]
TreeviewSelectCallback = Callable[[int], dict[str, Any]]
TreeviewActivateCallback = TreeviewSelectCallback
BoolCallback = Callable[[bool], dict[str, Any]]


def validate_choice(
    options: Mapping[str, Any],
    key: str,
    *,
    allowed: tuple[str, ...],
    default: str,
    widget: str,
) -> str:
    """Validate that ``options[key]`` is in *allowed*; else raise ValueError."""
    value = options.get(key, default)
    if value not in allowed:
        raise ValueError(
            f"invalid {key}={value!r} for {widget!r}: expected one of "
            f"{', '.join(repr(a) for a in allowed)}"
        )
    return str(value)


def validate_positive_int(
    options: Mapping[str, Any],
    key: str,
    *,
    default: int,
    widget: str,
) -> int:
    """Validate that ``options[key]`` is a positive int; else raise."""
    value = options.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(
            f"invalid {key}={value!r} for {widget!r}: expected a positive int"
        )
    return value


def normalize_treeview_columns(
    columns: list[Any] | tuple[Any, ...],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Parse column specs into Treeview column ids and heading configs."""
    ids: list[str] = []
    configs: list[dict[str, Any]] = []
    for col in columns:
        if isinstance(col, dict):
            cid = str(col["id"])
            ids.append(cid)
            configs.append({
                "id": cid,
                "heading": col.get("heading", cid),
                "width": col.get("width"),
                "anchor": col.get("anchor"),
                "stretch": bool(col.get("stretch", False)),
            })
        elif isinstance(col, (list, tuple)):
            cid = str(col[0])
            ids.append(cid)
            heading = str(col[1]) if len(col) > 1 else cid
            cfg: dict[str, Any] = {"id": cid, "heading": heading, "stretch": False}
            if len(col) > 2 and col[2] is not None:
                cfg["width"] = col[2]
            if len(col) > 3:
                cfg["anchor"] = col[3]
            configs.append(cfg)
        elif isinstance(col, str):
            cid = col
            ids.append(cid)
            configs.append({"id": cid, "heading": cid, "stretch": False})
        else:
            raise TypeError(f"Invalid treeview column: {col!r}")
    return ids, configs


class WidgetRegistrationMixin:
    """Provides @app.label, @app.button, etc., and app.add_* registration methods."""

    def _add_spec(self, spec: WidgetSpec) -> None:
        raise NotImplementedError

    def _widget_extras(
        self,
        extras: dict[str, Any] | None,
        *,
        takefocus: Any | None,
        widget_kwargs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _dispatch(self, spec_name: str, fn: Callable[..., Any], *args: Any) -> Any:
        raise NotImplementedError

    # ── widget registration decorators ──

    def label(
        self,
        name: str,
        **options: Unpack[LabelOptions],
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a label. Callback returns str or state dict."""
        def decorator(fn: LabelCallback) -> LabelCallback:
            extras: dict[str, Any] = {}
            font = options.get("font")
            anchor = options.get("anchor")
            justify = options.get("justify")
            padding = options.get("padding")
            width = options.get("width")
            if font is not None:
                extras["font"] = font
            if anchor is not None:
                extras["anchor"] = anchor
            if justify is not None:
                extras["justify"] = justify
            if padding is not None:
                extras["padding"] = padding
            if width is not None:
                extras["width"] = width
            if "text" in options and options["text"] is not None:
                extras["text"] = options["text"]
            self._add_spec(WidgetSpec(
                name=name, kind="label",
                role=options.get("role"),
                description=options.get("description"),
                on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=options.get("takefocus"),
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def status(
        self,
        name: str,
        **options: Unpack[LabelOptions],
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a label with ``role="status"``."""
        options["role"] = options.get("role", "status")
        return self.label(name, **options)

    def bind(
        self,
        name: str,
        **options: Any,
    ) -> Callable[[BindCallback], BindCallback]:
        """Register a global key binding."""
        sequence = options["sequence"]
        label = options.get("label", "")
        description = options.get("description")
        def decorator(fn: BindCallback) -> BindCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="bind", label_text=label,
                role="shortcut", description=description,
                on_click=lambda state: self._dispatch(name, fn, state),
                bindings=[(sequence, label)],
            ))
            return fn
        return decorator

    def message(
        self,
        name: str,
        **options: Unpack[MessageOptions],
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a message widget with wrap support."""
        def decorator(fn: LabelCallback) -> LabelCallback:
            width = options.get("width")
            extras: dict[str, Any] = {"auto_width": options.get("auto_width", True)}
            if width is not None:
                extras["width"] = width
            self._add_spec(WidgetSpec(
                name=name, kind="message",
                role=options.get("role"),
                description=options.get("description"),
                on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=options.get("takefocus"),
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def menubar(
        self,
        name: str = "menubar",
        **options: Any,
    ) -> Callable[[MenubarCallback], MenubarCallback]:
        """Register a native window menubar."""
        def decorator(fn: MenubarCallback) -> MenubarCallback:
            items = options.get("items")
            extras: dict[str, Any] = {}
            if items is not None:
                extras["items"] = list(items)
            self._add_spec(WidgetSpec(
                name=name, kind="menubar",
                description=options.get("description"),
                on_update=fn,
                extras=self._widget_extras(
                    extras,
                    takefocus=options.get("takefocus"),
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def filepicker(
        self,
        name: str,
        **options: Unpack[FilepickerOptions],
    ) -> Callable[[FilepickerCallback], FilepickerCallback]:
        """Register a file-chooser button."""
        def decorator(fn: FilepickerCallback) -> FilepickerCallback:
            label = options.get("label", "Choose File...")
            mode = validate_choice(
                options, "mode", allowed=("open", "open_multiple", "save", "directory"),
                default="open", widget=f"filepicker:{name}",
            )
            description = options.get("description")
            enabled_if = options.get("enabled_if")
            takefocus = options.get("takefocus")
            extras: dict[str, Any] = {"mode": mode}
            for opt in ("title", "initialdir", "initialfile", "filetypes", "defaultextension"):
                value = options.get(opt)  # type: ignore[literal-required]
                if value is not None:
                    extras[opt] = value
            self._add_spec(WidgetSpec(
                name=name, kind="filepicker", label_text=label, role="button",
                description=description, on_click=fn, enabled_if=enabled_if,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def button(
        self,
        name: str,
        **options: Any,
    ) -> Callable[[ButtonCallback], ButtonCallback]:
        """Register a button."""
        def decorator(fn: ButtonCallback) -> ButtonCallback:
            label = options.get("label", "")
            role = options.get("role", "button")
            description = options.get("description")
            state = options.get("state", "normal")
            enabled_if = options.get("enabled_if")
            takefocus = options.get("takefocus")
            primary = options.get("primary", False)
            font = options.get("font")
            extras: dict[str, Any] = {"style": "Primary.TButton" if primary else "Secondary.TButton"}
            if state != "normal":
                extras["state"] = state
            if font is not None:
                extras["font"] = font
            self._add_spec(WidgetSpec(
                name=name, kind="button", label_text=label, role=role,
                description=description, on_click=fn, enabled_if=enabled_if,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def entry(
        self,
        name: str,
        **options: Unpack[EntryOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register an entry field."""
        def decorator(fn: ValueCallback) -> ValueCallback:
            placeholder = options.get("placeholder", "")
            placeholder_as_hint = options.get("placeholder_as_hint", True)
            role = options.get("role")
            description = options.get("description")
            state = options.get("state", "normal")
            show = options.get("show")
            width = options.get("width")
            takefocus = options.get("takefocus")
            font = options.get("font")
            padding = options.get("padding")
            events = options.get("events")
            extras: dict[str, Any] = {}
            if show is not None:
                extras["show"] = show
            if width is not None:
                extras["width"] = width
            if state != "normal":
                extras["state"] = state
            if font is not None:
                extras["font"] = font
            if padding is not None:
                extras["padding"] = padding
            if events is not None:
                extras["events"] = events
            self._add_spec(WidgetSpec(
                name=name, kind="entry", placeholder=placeholder,
                placeholder_as_hint=placeholder_as_hint,
                role=role, description=description, on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def checkbutton(
        self,
        name: str,
        **options: Unpack[CheckbuttonOptions],
    ) -> Callable[[BoolCallback], BoolCallback]:
        """Register a checkbutton."""
        actual_key = options.get("key") or name
        text = options.get("text", "")
        description = options.get("description")
        takefocus = options.get("takefocus")
        font = options.get("font")
        def decorator(fn: BoolCallback) -> BoolCallback:
            extras: dict[str, Any] = {"state_key": actual_key}
            if font is not None:
                extras["font"] = font
            self._add_spec(WidgetSpec(
                name=name, kind="checkbutton", label_text=text,
                description=description, on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def radiobutton(
        self,
        name: str,
        **options: Unpack[RadiobuttonOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a radiobutton."""
        text = options.get("text", "")
        value = options.get("value", "")
        group = options.get("group", "radio")
        description = options.get("description")
        takefocus = options.get("takefocus")
        font = options.get("font")
        def decorator(fn: ValueCallback) -> ValueCallback:
            extras: dict[str, Any] = {"rb_value": value, "group_key": group}
            if font is not None:
                extras["font"] = font
            self._add_spec(WidgetSpec(
                name=name, kind="radiobutton", label_text=text,
                description=description, on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def text(
        self,
        name: str,
        **options: Unpack[TextOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a multiline text widget."""
        width = options.get("width", 50)
        height = options.get("height", 8)
        description = options.get("description")
        state = validate_choice(
            options, "state", allowed=("normal", "disabled", "active"),
            default="normal", widget=f"text:{name}",
        )
        tab_inserts = options.get("tab_inserts", False)
        readonly = options.get("readonly", False)
        tags = options.get("tags")
        sync_yscroll_with = options.get("sync_yscroll_with")
        takefocus = options.get("takefocus", True)
        font = options.get("font")
        wrap = validate_choice(
            options, "wrap", allowed=("word", "none", "char"),
            default="word", widget=f"text:{name}",
        )
        h_scroll = options.get("h_scroll", False)
        scrollbar = options.get("scrollbar", True)
        content = options.get("content")
        def decorator(fn: ValueCallback) -> ValueCallback:
            extras: dict[str, Any] = {"width": width, "height": height, "tab_inserts": tab_inserts}
            if state != "normal":
                extras["state"] = state
            if readonly:
                extras["readonly"] = True
            if tags is not None:
                extras["tags"] = tags
            if sync_yscroll_with is not None:
                extras["sync_yscroll_with"] = sync_yscroll_with
            if font is not None:
                extras["font"] = font
            if wrap != "word":
                extras["wrap"] = wrap
            if h_scroll:
                extras["h_scroll"] = True
            if not scrollbar:
                extras["scrollbar"] = False
            if content is not None:
                extras["content"] = str(content)
            self._add_spec(WidgetSpec(
                name=name, kind="text", description=description,
                on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def scale(
        self,
        name: str,
        **options: Unpack[ScaleOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a scale slider."""
        actual_key = options.get("key") or name
        from_ = options.get("from_", 0)
        to = options.get("to", 100)
        orient = validate_choice(
            options, "orient", allowed=("horizontal", "vertical"),
            default="horizontal", widget=f"scale:{name}",
        )
        description = options.get("description")
        takefocus = options.get("takefocus")
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="scale", description=description,
                on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras({
                    "state_key": actual_key, "from": from_,
                    "to": to, "orient": orient,
                }, takefocus=takefocus, widget_kwargs=options.get("widget_kwargs")),
            ))
            return fn
        return decorator

    def spinbox(
        self,
        name: str,
        **options: Unpack[SpinboxOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a spinbox."""
        actual_key = options.get("key") or name
        from_ = options.get("from_")
        to = options.get("to")
        values = options.get("values")
        width = options.get("width")
        description = options.get("description")
        takefocus = options.get("takefocus")
        font = options.get("font")
        def decorator(fn: ValueCallback) -> ValueCallback:
            extras: dict[str, Any] = {
                "state_key": actual_key, "from": from_,
                "to": to, "values": values,
            }
            if width is not None:
                extras["width"] = width
            if font is not None:
                extras["font"] = font
            self._add_spec(WidgetSpec(
                name=name, kind="spinbox", description=description,
                on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def combobox(
        self,
        name: str,
        **options: Unpack[ComboboxOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a ttk.Combobox."""
        actual_key = options.get("key") or name
        values = options.get("values")
        values_key = options.get("values_key")
        width = options.get("width")
        readonly = options.get("readonly", False)
        font = options.get("font")
        description = options.get("description")
        takefocus = options.get("takefocus")

        def decorator(fn: ValueCallback) -> ValueCallback:
            extras: dict[str, Any] = {
                "state_key": actual_key,
                "values": values or [],
                "readonly": readonly,
            }
            if values_key is not None:
                extras["values_key"] = values_key
            if width is not None:
                extras["width"] = width
            if font is not None:
                extras["font"] = font
            self._add_spec(WidgetSpec(
                name=name, kind="combobox", description=description,
                on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def listbox(
        self,
        name: str,
        **options: Unpack[ListboxOptions],
    ) -> Callable[[ListboxSelectCallback], ListboxSelectCallback]:
        """Register a listbox."""
        items = options.get("items")
        items_key = options.get("items_key")
        selectmode = validate_choice(
            options, "selectmode", allowed=("browse", "single", "multiple", "extended"),
            default="browse", widget=f"listbox:{name}",
        )
        height = options.get("height")
        description = options.get("description")
        enabled_if = options.get("enabled_if")
        events = options.get("events")
        takefocus = options.get("takefocus")
        font = options.get("font")
        def decorator(fn: ListboxSelectCallback) -> ListboxSelectCallback:
            extras: dict[str, Any] = {"items": items or [], "selectmode": selectmode}
            if items_key is not None:
                extras["items_key"] = items_key
            if height is not None:
                extras["height"] = height
            if events is not None:
                extras["events"] = events
            if font is not None:
                extras["font"] = font
            self._add_spec(WidgetSpec(
                name=name, kind="listbox", description=description,
                on_update=fn,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
                enabled_if=enabled_if,
            ))
            return fn
        return decorator

    def treeview(
        self,
        name: str,
        **options: Unpack[TreeviewOptions],
    ) -> Callable[[TreeviewSelectCallback], TreeviewSelectCallback]:
        """Register a flat ttk.Treeview table."""
        columns = options["columns"]
        rows_key = options.get("rows_key")
        selectmode = validate_choice(
            options, "selectmode", allowed=("single", "browse", "multiple", "extended"),
            default="browse", widget=f"treeview:{name}",
        )
        height = options.get("height", 8)
        description = options.get("description")
        activate = options.get("activate")
        double_click = options.get("double_click", True)
        takefocus = options.get("takefocus")
        col_ids, col_configs = normalize_treeview_columns(columns)
        actual_rows_key = rows_key or f"{name}_rows"

        def decorator(fn: TreeviewSelectCallback) -> TreeviewSelectCallback:
            extras: dict[str, Any] = {
                "column_ids": col_ids,
                "column_configs": col_configs,
                "rows_key": actual_rows_key,
                "selectmode": selectmode,
                "height": height,
                "double_click": bool(double_click),
            }
            self._add_spec(WidgetSpec(
                name=name, kind="treeview", description=description,
                on_update=fn, on_click=activate,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn
        return decorator

    def paned(
        self,
        name: str,
        **options: Unpack[PanedOptions],
    ) -> None:
        """Register a ttk.Panedwindow with named pane frames."""
        panes = options["panes"]
        orient = validate_choice(
            options, "orient", allowed=("horizontal", "vertical"),
            default="horizontal", widget=f"paned:{name}",
        )
        weights = options.get("weights")
        sashwidth = options.get("sashwidth", 4)
        description = options.get("description")
        pane_list = tuple(panes)
        weight_list = list(weights) if weights is not None else [1] * len(pane_list)
        self._add_spec(WidgetSpec(
            name=name, kind="paned", description=description,
            extras={
                "panes": pane_list,
                "orient": orient,
                "weights": weight_list,
                "sashwidth": sashwidth,
            },
        ))

    def progressbar(
        self,
        name: str,
        **options: Unpack[ProgressbarOptions],
    ) -> None:
        """Register a ttk.Progressbar driven by app state."""
        actual_key = options.get("key") or name
        maximum = options.get("maximum", 100.0)
        mode = validate_choice(
            options, "mode", allowed=("determinate", "indeterminate"),
            default="determinate", widget=f"progressbar:{name}",
        )
        length = options.get("length", 200)
        orient = validate_choice(
            options, "orient", allowed=("horizontal", "vertical"),
            default="horizontal", widget=f"progressbar:{name}",
        )
        description = options.get("description")
        self._add_spec(WidgetSpec(
            name=name, kind="progressbar", description=description,
            sync=options.get("sync", True),
            extras={
                "state_key": actual_key,
                "maximum": maximum,
                "mode": mode,
                "length": length,
                "orient": orient,
            },
        ))

    def canvas(
        self,
        name: str,
        **options: Unpack[CanvasOptions],
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Register a canvas (display only)."""
        width = options.get("width", 300)
        height = options.get("height", 200)
        bg = options.get("bg", t.SURFACE)
        description = options.get("description")
        items = options.get("items")
        takefocus = options.get("takefocus")
        def decorator(fn: Callable[[], None] | None = None) -> Callable[[], None]:
            extras: dict[str, Any] = {"width": width, "height": height, "bg": bg}
            if items:
                extras["items"] = items
            self._add_spec(WidgetSpec(
                name=name, kind="canvas", description=description,
                sync=options.get("sync", True),
                extras=self._widget_extras(
                    extras,
                    takefocus=takefocus,
                    widget_kwargs=options.get("widget_kwargs"),
                ),
            ))
            return fn  # type: ignore[return-value]
        return decorator

    # ── direct widget registration methods ──

    def add_label(self, name: str, **options: Unpack[LabelOptions]) -> None:
        """Register a label directly without a callback function."""
        text = options.get("text", "")
        self.label(name, **options)(lambda: str(text))

    def add_status(self, name: str, **options: Unpack[LabelOptions]) -> None:
        """Register a status label directly without a callback function."""
        text = options.get("text", "")
        self.status(name, **options)(lambda: str(text))

    def add_message(self, name: str, **options: Unpack[MessageOptions]) -> None:
        """Register a message widget directly without a callback function."""
        self.message(name, **options)(lambda: "")

    def add_button(
        self,
        name: str,
        on_click: ButtonCallback | None = None,
        **options: Any,
    ) -> None:
        """Register a button directly."""
        cb: ButtonCallback = on_click if on_click is not None else (lambda *_: {})
        self.button(name, **options)(cb)

    def add_entry(
        self,
        name: str,
        on_change: ValueCallback | None = None,
        **options: Unpack[EntryOptions],
    ) -> None:
        """Register an entry field directly."""
        cb: ValueCallback = on_change if on_change is not None else (lambda *_: {})
        self.entry(name, **options)(cb)

    def add_checkbutton(
        self,
        name: str,
        on_toggle: BoolCallback | None = None,
        **options: Unpack[CheckbuttonOptions],
    ) -> None:
        """Register a checkbutton directly."""
        cb: BoolCallback = on_toggle if on_toggle is not None else (lambda *_: {})
        self.checkbutton(name, **options)(cb)

    def add_radiobutton(
        self,
        name: str,
        on_select: ValueCallback | None = None,
        **options: Unpack[RadiobuttonOptions],
    ) -> None:
        """Register a radiobutton directly."""
        cb: ValueCallback = on_select if on_select is not None else (lambda *_: {})
        self.radiobutton(name, **options)(cb)

    def add_text(
        self,
        name: str,
        on_change: ValueCallback | None = None,
        **options: Unpack[TextOptions],
    ) -> None:
        """Register a text widget directly."""
        cb: ValueCallback = on_change if on_change is not None else (lambda *_: {})
        self.text(name, **options)(cb)

    def add_scale(
        self,
        name: str,
        on_change: ValueCallback | None = None,
        **options: Unpack[ScaleOptions],
    ) -> None:
        """Register a scale slider directly."""
        cb: ValueCallback = on_change if on_change is not None else (lambda *_: {})
        self.scale(name, **options)(cb)

    def add_spinbox(
        self,
        name: str,
        on_change: ValueCallback | None = None,
        **options: Unpack[SpinboxOptions],
    ) -> None:
        """Register a spinbox directly."""
        cb: ValueCallback = on_change if on_change is not None else (lambda *_: {})
        self.spinbox(name, **options)(cb)

    def add_combobox(
        self,
        name: str,
        on_select: ValueCallback | None = None,
        **options: Unpack[ComboboxOptions],
    ) -> None:
        """Register a combobox directly."""
        cb: ValueCallback = on_select if on_select is not None else (lambda *_: {})
        self.combobox(name, **options)(cb)

    def add_listbox(
        self,
        name: str,
        on_select: ListboxSelectCallback | None = None,
        **options: Unpack[ListboxOptions],
    ) -> None:
        """Register a listbox directly."""
        cb: ListboxSelectCallback = on_select if on_select is not None else (lambda *_: {})
        self.listbox(name, **options)(cb)

    def add_treeview(
        self,
        name: str,
        on_select: TreeviewSelectCallback | None = None,
        **options: Unpack[TreeviewOptions],
    ) -> None:
        """Register a treeview directly."""
        cb: TreeviewSelectCallback = on_select if on_select is not None else (lambda *_: {})
        self.treeview(name, **options)(cb)

    def add_canvas(self, name: str, **options: Unpack[CanvasOptions]) -> None:
        """Register a canvas directly."""
        self.canvas(name, **options)(lambda: None)

    def add_filepicker(
        self,
        name: str,
        on_pick: FilepickerCallback | None = None,
        **options: Unpack[FilepickerOptions],
    ) -> None:
        """Register a filepicker directly."""
        cb: FilepickerCallback = on_pick if on_pick is not None else (lambda *_: {})
        self.filepicker(name, **options)(cb)

    def add_progressbar(
        self,
        name: str,
        **options: Unpack[ProgressbarOptions],
    ) -> None:
        """Alias for :meth:`progressbar`."""
        self.progressbar(name, **options)
