"""Widget builders mixin for constructing ttk/tk widgets from WidgetSpec."""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
import unicodedata
from typing import TYPE_CHECKING, Any

from nextpytk import tokens as t
from nextpytk.tokens import PLACEHOLDER_FG
from nextpytk.types import OrientLike, WrapLike
from nextpytk.widgets import WidgetSpec


class WidgetBuildersMixin:
    """Provides methods for constructing underlying Tkinter/ttk widgets from WidgetSpec."""

    _root: tk.Tk | None
    _widgets: list[WidgetSpec]
    _tk_widgets: dict[str, tk.Widget]
    _text_inner: dict[str, tk.Text]
    _text_scrollbars: dict[str, ttk.Scrollbar | None]
    _text_hscrollbars: dict[str, ttk.Scrollbar]
    _text_scroll_sync: dict[str, str]
    _treeview_inner: dict[str, ttk.Treeview]
    _treeview_row_cache: dict[str, tuple[Any, ...]]
    _theme_tokens: t.ThemeTokens
    _kizashi: bool

    @property
    def _state(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def _tk_vars(self) -> dict[str, tk.Variable]:
        raise NotImplementedError

    def _register_var(self, key: str, var: tk.Variable) -> None:
        raise NotImplementedError

    def _dispatch(self, spec_name: str, fn: Any, *args: Any) -> Any:
        raise NotImplementedError

    def _apply_state(self, update: dict[str, Any]) -> None:
        raise NotImplementedError
    def _bind_message_auto_width(
        self,
        w: tk.Message,
        master: tk.Misc,
        *,
        max_ratio: float = 0.95,
        default_width: int = 200,
    ) -> None:
        """Bind resize events on the container so the Message width tracks the window width."""
        def _on_configure(_e: object = None) -> None:
            try:
                rw = master.winfo_width()
                if rw > 1:
                    w.configure(width=max(int(rw * max_ratio), default_width))
            except Exception:
                pass
        master.bind("<Configure>", _on_configure, add="+")
        if self._root is not None:
            self._root.bind("<Configure>", _on_configure, add="+")

    def _derive_ttk_style(
        self,
        base_style: str,
        style_name: str,
        overrides: dict[str, Any],
    ) -> str:
        """Create a unique derived ttk style that inherits the base layout."""
        if self._root is None:
            return base_style
        style = ttk.Style(self._root)
        style.layout(style_name, style.layout(base_style))
        style.configure(style_name, **overrides)
        return style_name

    def _invoke_filepicker(self, spec: WidgetSpec) -> None:
        """Open the file dialog for a filepicker spec and dispatch the result."""
        import tkinter.filedialog as fd

        mode = spec.extras.get("mode", "open")
        dialog_kw: dict[str, Any] = {}
        for opt in ("title", "initialdir", "initialfile", "filetypes", "defaultextension"):
            if opt in spec.extras:
                dialog_kw[opt] = spec.extras[opt]

        if mode == "open":
            result = fd.askopenfilename(**dialog_kw)
        elif mode == "open_multiple":
            result = fd.askopenfilenames(**dialog_kw)
        elif mode == "save":
            result = fd.asksaveasfilename(**dialog_kw)
        elif mode == "directory":
            result = fd.askdirectory(**dialog_kw)
        else:
            raise ValueError(f"unknown filepicker mode {mode!r}")
        if result == "" or result == () or result is None:
            result = None
        fn = spec.on_click
        if fn is None:
            return
        out = self._dispatch(spec.name, fn, result)
        if isinstance(out, dict) and out:
            self._apply_state(out)

    def _build_filepicker(self, spec: WidgetSpec, master: tk.Misc) -> None:
        """Build a button that opens a file dialog when clicked."""
        style = spec.extras.get("style", "Secondary.TButton")
        overrides: dict[str, Any] = {}
        if "font" in spec.extras:
            overrides["font"] = spec.extras["font"]
        if overrides:
            style = self._derive_ttk_style(
                style, f"Unique.{style}.{spec.name}", overrides
            )
        w = ttk.Button(master, text=spec.label_text or spec.name, style=style)
        if "state" in spec.extras:
            w.configure(state=spec.extras["state"])
        self._tk_widgets[spec.name] = w
        w.configure(command=lambda s=spec: self._invoke_filepicker(s))

    def _build_entry(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        var = tk.StringVar(value="")
        style = "TEntry"
        overrides: dict[str, Any] = {}
        if "font" in e:
            overrides["font"] = e["font"]
        if "padding" in e:
            overrides["padding"] = e["padding"]
        if overrides:
            style = self._derive_ttk_style(
                style, f"Unique.{style}.{spec.name}", overrides
            )
        w = ttk.Entry(master, textvariable=var, style=style)
        self._tk_widgets[spec.name] = w
        self._register_var(spec.name, var)
        for opt in ("show", "width", "state"):
            if opt in e:
                w.configure(**{opt: e[opt]})
        if spec.placeholder_as_hint and spec.placeholder:
            ph = spec.placeholder
            var.set(ph)
            setattr(w, "_nextpytk_ph_active", True)
            setattr(w, "_nextpytk_placeholder", ph)
            try:
                setattr(w, "_nextpytk_fg_normal", w.cget("foreground"))
                w.configure(foreground=PLACEHOLDER_FG)
            except Exception:
                setattr(w, "_nextpytk_fg_normal", None)
            w.bind("<FocusIn>", lambda _e, n=spec.name: getattr(self, "_entry_focus_in")(n))
            w.bind("<FocusOut>", lambda _e, n=spec.name: getattr(self, "_entry_focus_out")(n))
        if spec.on_update is not None:
            fn = spec.on_update
            w.bind("<KeyRelease>", lambda _e, s=spec, f=fn: getattr(self, "_on_entry_change")(s, f))
        for sequence, handler in e.get("events", {}).items():
            w.bind(sequence, lambda _e, h=handler: getattr(self, "_on_entry_event")(h))

    def _build_checkbutton(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        var = tk.StringVar(value="0")
        overrides: dict[str, Any] = {}
        if "font" in e:
            overrides["font"] = e["font"]
        w = ttk.Checkbutton(
            master,
            text=spec.label_text,
            variable=var,
            onvalue="1",
            offvalue="0",
        )
        if overrides:
            style = self._derive_ttk_style(
                "TCheckbutton", f"Unique.TCheckbutton.{spec.name}", overrides
            )
            w.configure(style=style)
        self._tk_widgets[spec.name] = w
        self._register_var(key, var)
        if spec.on_update is not None:
            fn = spec.on_update
            w.configure(command=lambda s=spec, f=fn, v=var, k=key:
                        getattr(self, "_on_checkbutton_change")(s, f, v, k))

    def _build_radiobutton(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        group = e.get("group_key", "radio")
        val = str(e.get("rb_value", ""))
        var = self._tk_vars.get(group)
        if var is None:
            var = tk.StringVar(value="")
            self._register_var(group, var)
        overrides: dict[str, Any] = {}
        if "font" in e:
            overrides["font"] = e["font"]
        w = ttk.Radiobutton(
            master,
            text=spec.label_text,
            value=val,
            variable=var,
        )
        if overrides:
            style = self._derive_ttk_style(
                "TRadiobutton", f"Unique.TRadiobutton.{spec.name}", overrides
            )
            w.configure(style=style)
        self._tk_widgets[spec.name] = w
        if spec.on_update is not None:
            fn = spec.on_update
            w.configure(command=lambda s=spec, f=fn, v=var, k=group:
                        getattr(self, "_on_radiobutton_change")(s, f, v, k))

    def _build_text(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        container = ttk.Frame(master)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        wrap: WrapLike = e.get("wrap", "word")

        w = tk.Text(
            container,
            width=e.get("width", 50),
            height=e.get("height", 8),
            name=spec.name,
            bg=t.SURFACE,
            fg=t.TEXT,
            insertbackground=t.TEXT,
            selectbackground=t.ACCENT_RAMP[200],
            selectforeground=t.ACCENT_RAMP[700],
            relief="solid",
            bd=1,
            highlightthickness=0,
            font=t.font("body"),
            wrap=wrap,
        )
        if e.get("font") is not None:
            w.configure(font=e["font"])
        scroll: ttk.Scrollbar | None = None
        if e.get("scrollbar", True):
            scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=w.yview)
            w.configure(yscrollcommand=scroll.set)
            scroll.grid(row=0, column=1, sticky="ns")
        w.grid(row=0, column=0, sticky="nsew")
        h_scroll = e.get("h_scroll", False)
        if h_scroll:
            hsb = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=w.xview)
            w.configure(xscrollcommand=hsb.set)
            hsb.grid(row=1, column=0, columnspan=2, sticky="ew")
            container.rowconfigure(1, weight=0)
            self._text_hscrollbars[spec.name] = hsb
        self._tk_widgets[spec.name] = container
        self._text_inner[spec.name] = w
        self._text_scrollbars[spec.name] = scroll
        tags: dict[str, dict[str, Any]] | None = e.get("tags")
        if tags:
            for tag_name, tag_kw in tags.items():
                w.tag_config(tag_name, **tag_kw)

        if "content" in e and e["content"]:
            w.insert("1.0", str(e["content"]))

        if e.get("readonly"):
            w.bind("<Key>", lambda _e: "break")
            w.bind("<Button-1>", lambda _e: "break")
            w.bind("<B1-Motion>", lambda _e: "break")

        sync_with: str | None = e.get("sync_yscroll_with")
        if sync_with is not None:
            self._text_scroll_sync[spec.name] = sync_with

        if not e.get("tab_inserts", False):
            def _focus_tab(_event: tk.Event[tk.Misc], ww: tk.Text) -> str:
                nxt = ww.tk_focusNext()
                if nxt is not None:
                    nxt.focus_set()
                return "break"

            def _focus_shift_tab(_event: tk.Event[tk.Misc], ww: tk.Text) -> str:
                prv = ww.tk_focusPrev()
                if prv is not None:
                    prv.focus_set()
                return "break"

            w.bind("<Tab>", lambda e, ww=w: _focus_tab(e, ww))
            w.bind("<Shift-Tab>", lambda e, ww=w: _focus_shift_tab(e, ww))
            w.bind("<Control-Tab>", lambda _e: None)
            w.bind("<Control-Shift-Tab>", lambda _e: None)
        if spec.on_update is not None:
            fn = spec.on_update
            w.bind("<KeyRelease>", lambda _e, s=spec, f=fn:
                   getattr(self, "_on_text_change")(s, f))

    def _build_scale(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        var = tk.IntVar(value=int(e.get("from", 0)))
        orient_str: OrientLike = e.get("orient", "horizontal")
        w = ttk.Scale(
            master,
            from_=e.get("from", 0),
            to=e.get("to", 100),
            orient=orient_str,
            variable=var,
            length=e.get("length", 200 if orient_str == "horizontal" else 100),
        )  # type: ignore[arg-type]
        self._tk_widgets[spec.name] = w
        self._register_var(key, var)
        self._state[key] = str(var.get())
        if spec.on_update is not None:
            fn = spec.on_update
            var.trace_add("write", lambda *_a, s=spec, f=fn, v=var, k=key:
                          getattr(self, "_on_var_change")(s, f, v, k))

    def _build_spinbox(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        init_val = ""
        if e.get("values"):
            vals = e.get("values", [])
            if isinstance(vals, list) and vals:
                init_val = str(vals[0])
        elif e.get("from") is not None:
            init_val = str(e.get("from"))
        var = tk.StringVar(value=init_val)
        kwargs: dict[str, Any] = {}
        if e.get("from") is not None:
            kwargs["from_"] = e["from"]
        if e.get("to") is not None:
            kwargs["to"] = e["to"]
        if e.get("values"):
            kwargs["values"] = e["values"]
        if e.get("width") is not None:
            kwargs["width"] = e["width"]
        if e.get("font") is not None:
            kwargs["font"] = e["font"]
        w = ttk.Spinbox(master, textvariable=var, **kwargs)
        self._tk_widgets[spec.name] = w
        self._register_var(key, var)
        if init_val:
            self._state[key] = init_val
        if spec.on_update is not None:
            fn = spec.on_update
            var.trace_add("write", lambda *_a, s=spec, f=fn, v=var, k=key:
                          getattr(self, "_on_var_change")(s, f, v, k))

    def _build_combobox(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        values = getattr(self, "_combobox_values")(spec) if hasattr(self, "_combobox_values") else e.get("values", [])
        init_val = str(values[0]) if values else ""
        var = tk.StringVar(value=init_val)
        kwargs: dict[str, Any] = {
            "values": values,
            "textvariable": var,
            "width": e.get("width", t.DEFAULT_COMBOBOX_WIDTH),
        }
        if e.get("readonly"):
            kwargs["state"] = "readonly"
            kwargs["style"] = "Readonly.TCombobox"
        if e.get("font") is not None:
            kwargs["font"] = e["font"]
        w = ttk.Combobox(master, **kwargs)
        self._tk_widgets[spec.name] = w
        self._register_var(key, var)
        if init_val:
            self._state[key] = init_val
        if spec.on_update is not None:
            fn = spec.on_update
            var.trace_add("write", lambda *_a, s=spec, f=fn, v=var, k=key:
                          getattr(self, "_on_var_change")(s, f, v, k))

    def _build_listbox(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        kwargs_lb: dict[str, Any] = {
            "bg": t.BG,
            "fg": t.TEXT,
            "selectbackground": t.ACCENT_RAMP[200],
            "selectforeground": t.ACCENT_RAMP[700],
            "relief": "solid",
            "bd": 1,
            "highlightthickness": 0,
            "font": t.font("body"),
        }
        if e.get("height") is not None:
            kwargs_lb["height"] = e["height"]
        else:
            kwargs_lb["height"] = t.DEFAULT_LISTBOX_ROWS
        if e.get("selectmode"):
            kwargs_lb["selectmode"] = e["selectmode"]
        if e.get("font") is not None:
            kwargs_lb["font"] = e["font"]
        w = tk.Listbox(master, name=spec.name, **kwargs_lb)
        items = getattr(self, "_listbox_items")(spec) if hasattr(self, "_listbox_items") else e.get("items", [])
        for item in items:
            w.insert("end", item)
        self._tk_widgets[spec.name] = w
        if spec.name not in self._state:
            self._state[spec.name] = -1
        if spec.on_update is not None:
            fn = spec.on_update
            w.bind("<<ListboxSelect>>", lambda _e, s=spec, f=fn:
                   getattr(self, "_on_listbox_select")(s, f))
        for sequence, handler in e.get("events", {}).items():
            w.bind(sequence, lambda _e, h=handler: getattr(self, "_on_listbox_event")(h))
        if hasattr(self, "_sync_listbox_items"):
            getattr(self, "_sync_listbox_items")(spec)

    def _build_treeview(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        col_ids: list[str] = e.get("column_ids", [])
        col_configs: list[dict[str, Any]] = e.get("column_configs", [])
        container = ttk.Frame(master)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        kwargs_tv: dict[str, Any] = {
            "columns": col_ids,
            "show": "headings",
            "selectmode": e.get("selectmode", "browse"),
        }
        if e.get("height"):
            kwargs_tv["height"] = e["height"]
        tree = ttk.Treeview(container, name=spec.name, **kwargs_tv)
        for cfg in col_configs:
            cid = cfg["id"]
            tree.heading(cid, text=cfg["heading"])
            col_kw: dict[str, Any] = {}
            if cfg.get("width") is not None:
                col_kw["width"] = cfg["width"]
            if cfg.get("anchor"):
                col_kw["anchor"] = cfg["anchor"]
            if cfg.get("stretch"):
                col_kw["stretch"] = True
            tree.column(cid, **col_kw)
        scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self._tk_widgets[spec.name] = container
        self._treeview_inner[spec.name] = tree
        if spec.on_update is not None:
            fn = spec.on_update
            tree.bind(
                "<ButtonRelease-1>",
                lambda ev, s=spec, f=fn: getattr(self, "_on_treeview_click")(s, f, ev),
            )
        if spec.on_click is not None:
            fn_activate = spec.on_click
            if e.get("double_click", True):
                tree.bind(
                    "<Double-1>",
                    lambda _e, s=spec, f=fn_activate: getattr(self, "_on_treeview_activate")(s, f),
                )
            else:
                tree.bind(
                    "<ButtonRelease-1>",
                    lambda ev, s=spec, f=fn_activate: getattr(self, "_on_treeview_activate")(s, f, ev),
                )
        if hasattr(self, "_sync_treeviews"):
            getattr(self, "_sync_treeviews")(force=True)

    def _build_paned(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        orient: OrientLike = e.get("orient", "horizontal")
        pw = ttk.Panedwindow(master, orient=orient)
        self._tk_widgets[spec.name] = pw
        for pane_id in e.get("panes", ()):
            pane_frame = tk.Frame(pw, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
            self._tk_widgets[pane_id] = pane_frame

    def _build_progressbar(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        maximum = float(e.get("maximum", 100))
        orient_str: OrientLike = e.get("orient", "horizontal")
        length = int(e.get("length", 200))
        pb_mode = e.get("mode", "determinate")
        w = ttk.Progressbar(
            master,
            orient=orient_str,  # type: ignore[arg-type]
            length=length,
            mode=pb_mode,
            maximum=maximum,
        )
        self._tk_widgets[spec.name] = w
        raw = self._state.get(key, 0)
        try:
            init = float(raw)
        except (TypeError, ValueError):
            init = 0.0
        w.configure(value=max(0.0, min(maximum, init)))

    def _build_canvas(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        w = tk.Canvas(
            master,
            width=e.get("width", 300),
            height=e.get("height", 200),
            bg=e.get("bg", t.SURFACE),
            name=spec.name,
            highlightthickness=0,
        )
        self._tk_widgets[spec.name] = w

    def _build_bind(self, spec: WidgetSpec, master: tk.Misc) -> None:
        self._register_bind(spec)

    def _register_bind(self, spec: WidgetSpec) -> None:
        """Apply a global key binding registered via @app.bind."""
        if self._root is None or spec.on_click is None:
            return
        for sequence, _label in spec.bindings:
            fn = spec.on_click
            self._root.bind_all(sequence, lambda _e, f=fn, s=spec: getattr(self, "_on_bind_trigger")(s, f), add="+")

    def _annotate_button_shortcuts(self) -> None:
        """Append shortcut labels to button text when bind name matches."""
        bind_map: dict[str, str] = {}
        for spec in self._widgets:
            if spec.kind == "bind" and spec.bindings:
                shortcut_label = spec.bindings[0][1]
                if shortcut_label:
                    bind_map[spec.name] = shortcut_label
        for spec in self._widgets:
            if spec.kind == "button" and spec.name in bind_map:
                w = self._tk_widgets.get(spec.name)
                if isinstance(w, (tk.Button, ttk.Button)):
                    shortcut = bind_map[spec.name]
                    current = str(w.cget("text"))
                    if shortcut not in current:
                        w.configure(text=f"{current} ({shortcut})")

    def _build_label(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        style = "Heading.TLabel" if spec.role == "heading" else "TLabel"
        default_anchor = "w" if self._kizashi else "center"
        default_justify = "left" if self._kizashi else "center"
        w = ttk.Label(master, text="", anchor=default_anchor, justify=default_justify, style=style)
        for opt in ("font", "anchor", "justify", "padding", "width"):
            if opt in e:
                w.configure(**{opt: e[opt]})
        self._tk_widgets[spec.name] = w
        if spec.on_update is not None:
            result = self._dispatch(spec.name, spec.on_update)
            text = ""
            if isinstance(result, str):
                text = result
            elif isinstance(result, dict):
                text = str(result.get(spec.name, ""))
            w.configure(text=text)
            if "width" not in e:
                def _display_width(s: str) -> int:
                    width = 0
                    for ch in s:
                        eaw = unicodedata.east_asian_width(ch)
                        width += 2 if eaw in ("F", "W") else 1
                    return width
                try:
                    w.configure(width=_display_width(text))
                except Exception:
                    pass

    def _build_message(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        w = tk.Message(
            master,
            text="",
            name=spec.name,
            bg=t.BG,
            fg=t.TEXT,
            font=t.font("body"),
            anchor="w",
            justify="left",
        )
        self._tk_widgets[spec.name] = w
        if e.get("width") is not None:
            w.configure(width=e["width"])
        if e.get("auto_width", True):
            self._bind_message_auto_width(w, master)
        if spec.on_update is not None:
            result = self._dispatch(spec.name, spec.on_update)
            if isinstance(result, str):
                w.configure(text=result)
            elif isinstance(result, dict):
                w.configure(text=str(result.get(spec.name, "")))

    def _build_button(self, spec: WidgetSpec, master: tk.Misc) -> None:
        style = spec.extras.get("style", "Secondary.TButton")
        overrides: dict[str, Any] = {}
        if "font" in spec.extras:
            overrides["font"] = spec.extras["font"]
        if overrides:
            style = self._derive_ttk_style(
                style, f"Unique.{style}.{spec.name}", overrides
            )
        w = ttk.Button(master, text=spec.label_text or spec.name, style=style)
        if "state" in spec.extras:
            w.configure(state=spec.extras["state"])
        self._tk_widgets[spec.name] = w
        if spec.on_click is not None:
            fn = spec.on_click
            w.configure(command=lambda s=spec, f=fn: getattr(self, "_on_button_click")(s, f))
