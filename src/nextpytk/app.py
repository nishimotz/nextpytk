"""TkApp: accessible, declarative Tkinter apps from ordinary Python functions.

Core idea:
- ``@app.label`` / ``@app.status`` / ``@app.button`` / ``@app.entry`` /
  ``@app.checkbutton`` / ``@app.radiobutton`` / ``@app.text`` /
  ``@app.scale`` / ``@app.spinbox`` / ``@app.listbox`` / ``@app.treeview`` /
  ``app.paned`` / ``app.progressbar`` register slots.
- Python owns nothing but schema + callbacks. Widget objects live in tkinter.
- Each decorated function returns a dict that merges into app's state.
- Layout is injected separately via Layout.
- ``app.schema()`` exports the same structure for agents and tools.
  The decorator style is Flask-inspired.
"""

from __future__ import annotations

import asyncio
import sys
import tkinter as tk
import tkinter.ttk as ttk
import traceback
import unicodedata
import warnings
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeVar

ProgressModeLike = Literal["determinate", "indeterminate"]

from nextpytk import tokens as t
from nextpytk.tokens import PLACEHOLDER_FG
from nextpytk.types import (
    BindOptions,
    ButtonOptions,
    CanvasOptions,
    CheckbuttonOptions,
    ComboboxOptions,
    EntryOptions,
    EventSeq,
    FillLike,
    LabelOptions,
    ListboxEventHandler,
    ListboxOptions,
    ListboxSelectCallback,
    MenubarCallback,
    MenubarOptions,
    MessageOptions,
    OrientLike,
    PanedOptions,
    ProgressbarOptions,
    RadiobuttonOptions,
    ScaleOptions,
    SelectModeLike,
    SideLike,
    SpinboxOptions,
    StateLike,
    TakeFocusLike,
    TextOptions,
    TreeviewOptions,
    Unpack,
)
from nextpytk.widgets import WidgetSpec

if TYPE_CHECKING:
    from nextpytk.layout import Layout, LayoutBuilder

# ── asyncio helper: wrapper around root.after for async scheduling ──
TkAppAfterHandle: TypeAlias = str  # root.after returns a string id

# ── async job type alias ──
AsyncJob = Callable[..., Awaitable[dict[str, Any] | None]]

F = TypeVar("F", bound=Callable[..., Any])
NotebookTabChange = Callable[[str], dict[str, Any] | None]


def _levenshtein(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


# ── callback type aliases ──

# label/status: no arg, returns str or state dict
LabelCallback = Callable[[], str | dict[str, Any]]

# button: receives entry values dict, returns state dict
ButtonCallback = Callable[[dict[str, Any]], dict[str, Any]]
BindCallback = ButtonCallback  # bind: same signature: state dict → state dict

# entry / text / scale / spinbox: receives value str, returns state dict
ValueCallback = Callable[[str], dict[str, Any]]

# treeview: receives selected row index (-1 if none), returns state dict
TreeviewSelectCallback = Callable[[int], dict[str, Any]]
TreeviewActivateCallback = TreeviewSelectCallback

# checkbutton: receives bool, returns state dict
BoolCallback = Callable[[bool], dict[str, Any]]


def _normalize_treeview_columns(
    columns: list[Any],
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
        else:
            raise TypeError(f"Invalid treeview column: {col!r}")
    return ids, configs

# radiobutton: receives selected value str, returns state dict


class _PaneContext:
    """Context manager for ``with app.pane(\"left\"):``."""

    def __init__(self, app: TkApp, pane_id: str) -> None:
        self._app = app
        self._pane_id = pane_id
        self._prev: str | None = None

    def __enter__(self) -> _PaneContext:
        self._prev = self._app._current_pane
        self._app._current_pane = self._pane_id
        return self

    def __exit__(self, *_args: object) -> None:
        self._app._current_pane = self._prev


class ViewContext:
    """Context manager for ``with app.view(name) as v:``.

    Proxies all ``@app.*`` decorator methods and records registered
    widget names in ``app._view_widgets[name]``.
    """

    def __init__(self, app: TkApp, name: str):
        self._app = app
        self._name = name

    def __enter__(self) -> ViewContext:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    _PROXIED = frozenset({
        "label", "status", "message", "button", "bind", "entry",
        "checkbutton", "radiobutton", "text", "scale", "spinbox",
        "listbox", "combobox", "treeview", "paned", "progressbar", "canvas",
        "menubar",
    })

    def pane(self, pane_id: str) -> _PaneContext:
        return self._app.pane(pane_id)

    def __getattr__(self, attr: str) -> Any:
        """Proxy widget-registration methods, recording names in this view."""
        if attr not in self._PROXIED:
            raise AttributeError(
                f"{type(self).__name__!s} has no attribute {attr!r}"
            )
        target = getattr(self._app, attr)

        def register_and_delegate(name: str, **kw: Any) -> Any:
            self._app._view_widgets[self._name].append(name)
            return target(name, **kw)

        return register_and_delegate


class TkApp:
    """Tk application: register widgets as functions, declare layout separately.

    Decorators register intent; Layout provides structure. The writing style
    is Flask-inspired.
    """

    def __init__(
        self,
        title: str = "nextpytk",
        *,
        debug: bool = False,
        theme: bool | str = "kizashi",
    ):
        self._title = title
        self._debug = debug
        self._theme = self._normalize_theme(theme)
        self._kizashi = self._theme == "kizashi"
        self._acc_supported: bool | None = None
        self._widgets: list[WidgetSpec] = []
        self._state: dict[str, Any] = {}
        self._root: tk.Tk | None = None
        self._tk_widgets: dict[str, tk.Widget] = {}
        self._tk_vars: dict[str, tk.Variable] = {}
        self._widget_masters: dict[str, tk.Misc] = {}
        self._row_pack_jobs: list[tuple[tk.Frame, Any]] = []
        self._grid_pack_jobs: list[tuple[tk.Frame, Any]] = []
        self._view_widgets: dict[str, list[str]] = {}
        self._view_layouts: dict[str, Layout] = {}
        self._multiviews: dict[str, dict[str, Any]] = {}
        self._current_view: str | None = None
        self._stages: dict[str, dict[str, Any]] = {}
        self._current_stage: str | None = None
        self._stage_container: tk.Frame | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._jobs: dict[str, AsyncJob] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._treeview_inner: dict[str, ttk.Treeview] = {}
        self._treeview_row_cache: dict[str, tuple[Any, ...]] = {}
        self._text_inner: dict[str, tk.Text] = {}
        self._text_scroll_sync: dict[str, str] = {}
        self._paned_inner: dict[str, ttk.Panedwindow] = {}
        self._pane_frames: dict[str, tk.Widget] = {}
        self._layout_paned_opts: dict[str, dict[str, Any]] = {}
        self._current_pane: str | None = None
        self._menubar_submenus: dict[str | int, list[tk.Menu | None]] = {}
        self._declared_state_keys: set[str] = set()
        self._warned_state_keys: set[str] = set()
        self._first_focusable: tk.Widget | None = None
        self._register_default_builders()

    def _normalize_theme(self, theme: bool | str) -> str:
        """Convert the legacy bool ``theme=`` parameter to theme names.

        - ``True`` -> ``"kizashi"`` (the nextpytk design system theme)
        - ``False`` -> ``"none"`` (do not touch ttk styles at all)
        - ``str`` -> passed through; use ``"kizashi"``, ``"none"``,
          or any built-in ttk theme name (``"clam"``, ``"vista"``, ...).

        Passing a bool is deprecated and will be removed in v0.5.0.
        """
        if isinstance(theme, bool):
            warnings.warn(
                "theme=True/False is deprecated; use theme='kizashi' or "
                "theme='none' (bool support will be removed in v0.5.0).",
                DeprecationWarning,
                stacklevel=3,
            )
            return "kizashi" if theme else "none"
        if not isinstance(theme, str):
            raise TypeError(f"theme must be bool or str, got {type(theme).__name__}")
        return theme

    def clear_runtime(self) -> None:
        self._tk_widgets.clear()
        self._treeview_inner.clear()
        self._treeview_row_cache.clear()
        self._paned_inner.clear()
        self._pane_frames.clear()
        self._layout_paned_opts.clear()
        self._current_pane = None
        self._tk_vars.clear()
        self._widget_masters.clear()
        self._row_pack_jobs.clear()
        self._grid_pack_jobs.clear()
        self._menubar_submenus.clear()
        self._text_inner.clear()
        self._text_scroll_sync.clear()
        self._current_view = None
        self._current_stage = None
        self._first_focusable = None

    def pane(self, pane_id: str) -> _PaneContext:
        """Context manager: register following widgets inside a ``@app.paned`` pane."""
        return _PaneContext(self, pane_id)

    def _add_spec(self, spec: WidgetSpec) -> None:
        """Register a WidgetSpec, rejecting duplicate names.

        ``bind`` specs are exempt: a bind sharing a button's name is the
        documented pairing for shortcut annotation.
        """
        if spec.kind != "bind":
            for w in self._widgets:
                if w.name == spec.name and w.kind != "bind":
                    raise ValueError(
                        f"widget name {spec.name!r} is already registered "
                        f"(kind={w.kind!r})"
                    )
        self._widgets.append(spec)

    def _dispatch(self, spec_name: str, fn: Callable[..., Any],
                  *args: Any) -> Any:
        """Run a user callback under the framework error policy.

        Exceptions are never swallowed silently: the traceback always goes
        to stderr, and ``TkApp(debug=True)`` re-raises.
        Returns the callback result, or ``None`` after a handled error.
        """
        try:
            return fn(*args)
        except Exception:
            print(f"nextpytk: error in callback for {spec_name!r}:",
                  file=sys.stderr)
            traceback.print_exc()
            if self._debug:
                raise
            return None

    def _merge_widget_extras(self, extras: dict[str, Any]) -> dict[str, Any]:
        out = dict(extras)
        if self._current_pane is not None:
            out["pane"] = self._current_pane
        return out

    def _widget_extras(
        self,
        extras: dict[str, Any] | None = None,
        *,
        takefocus: TakeFocusLike | None = None,
    ) -> dict[str, Any]:
        """Merge layout pane id and optional ``takefocus`` into widget extras."""
        out = dict(extras or {})
        if takefocus is not None:
            out["takefocus"] = takefocus
        return self._merge_widget_extras(out)

    @staticmethod
    def _normalize_takefocus(value: TakeFocusLike) -> str | int:
        if value is True:
            return 1
        if value is False:
            return 0
        return value

    def _takefocus_widget(self, spec: WidgetSpec) -> tk.Widget | None:
        if spec.kind in ("bind", "paned", "progressbar"):
            return None
        if spec.kind == "treeview":
            return self._treeview_inner.get(spec.name)
        if spec.kind == "text":
            return self._text_inner.get(spec.name)
        return self._tk_widgets.get(spec.name)

    def _apply_all_takefocus(self) -> None:
        for spec in self._widgets:
            if "takefocus" not in spec.extras:
                continue
            w = self._takefocus_widget(spec)
            if w is None:
                continue
            tf = self._normalize_takefocus(spec.extras["takefocus"])
            try:
                w.configure({"takefocus": tf})
            except tk.TclError:
                pass

    def view(self, name: str, *, layout: Layout | None = None) -> ViewContext:
        """Context manager for grouping widgets (e.g., a tab).

        Usage::

            with app.view("Settings") as v:
                @v.status("msg")
                def msg(): return "idle"
        """
        if name not in self._view_widgets:
            self._view_widgets[name] = []
        if layout is not None:
            self._view_layouts[name] = layout
        return ViewContext(self, name)

    # ── public runtime helpers (for advanced custom runners) ──

    @property
    def title(self) -> str:
        return self._title

    def _configure_theme(self, root: tk.Tk) -> None:
        """Apply the configured theme and window chrome to ``root``.

        - ``"kizashi"`` applies the Kizashi design system.
        - any other theme name applies it via ``ttk.Style.theme_use``.
        - ``"none"`` does not touch ttk styles at all.

        Unknown theme names are silently ignored; a warning would be a
        future improvement.
        """
        if self._theme == "none":
            return
        from nextpytk.theme import _set_windows_dpi_aware, configure_window
        _set_windows_dpi_aware()
        if self._kizashi:
            from nextpytk.theme import apply_theme
            apply_theme(root)
        else:
            style = ttk.Style(root)
            try:
                style.theme_use(self._theme)
            except tk.TclError:
                warnings.warn(
                    f"ttk theme '{self._theme}' is not available; "
                    "falling back to the platform default.",
                    UserWarning,
                    stacklevel=3,
                )
        configure_window(root, title=self._title)

    def set_root(self, root: tk.Tk) -> None:
        self._root = root
        self._configure_theme(root)

    def set_widget_master(self, widget_name: str, master: tk.Misc) -> None:
        self._widget_masters[widget_name] = master

    def view_widget_names(self, view_name: str) -> list[str]:
        return list(self._view_widgets.get(view_name, []))

    def view_layout(self, view_name: str) -> Layout | None:
        return self._view_layouts.get(view_name)

    def multiview(
        self,
        name: str,
        *,
        views: list[str],
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
        on_tab_change: NotebookTabChange | None = None,
        tabposition: str = "nw",
    ) -> Callable[[F], F]:
        """Declare a multiview configuration by name.

        ``tabposition`` controls where the Notebook tabs are rendered.
        One of ``nw`` (top-left, default), ``n``, ``ne``, ``w`` (left),
        ``e`` (right), ``sw``, ``s``, ``se``.

        Example::

            @app.multiview("main", views=["Home", "Settings"],
                            tabposition="w")
            def _main_tabs():
                pass

            app.run(multiview="main")
        """
        cfg: dict[str, Any] = {
            "views": list(views),
            "toplevel_widgets": tuple(toplevel_widgets),
            "initial_state": dict(initial_state) if initial_state else None,
            "view_layouts": dict(view_layouts) if view_layouts else None,
            "center_kinds": set(center_kinds) if center_kinds else None,
            "on_tab_change": on_tab_change,
            "tabposition": tabposition,
        }
        self._multiviews[name] = cfg

        def decorator(fn: F) -> F:
            return fn

        return decorator

    def stages(
        self,
        name: str,
        *,
        stages: list[str],
        key: str,
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
    ) -> Callable[[F], F]:
        """Declare a state-driven stage configuration by name.

        Only one stage is visible at a time.  The active stage is selected
        by ``state[key]`` and changes via ``apply_state`` rerender the body
        without creating a new root window.

        Example::

            @app.stages("main", stages=["home", "settings"], key="screen")
            def _main_stages():
                pass

            app.run(stages="main")

        Widgets that belong to every stage can be declared outside any view
        and listed in ``toplevel_widgets``; they stay put while the body swaps.
        """
        cfg: dict[str, Any] = {
            "stages": list(stages),
            "key": key,
            "toplevel_widgets": tuple(toplevel_widgets),
            "initial_state": dict(initial_state) if initial_state else None,
            "view_layouts": dict(view_layouts) if view_layouts else None,
            "center_kinds": set(center_kinds) if center_kinds else None,
        }
        self._stages[name] = cfg

        def decorator(fn: F) -> F:
            return fn

        return decorator

    def build_widgets(self) -> None:
        self._build_widgets()

    def widget(self, name: str) -> tk.Widget | None:
        return self._tk_widgets.get(name)

    def text_widget(self, name: str) -> tk.Text | None:
        """Return the real ``tk.Text`` widget for a registered text widget.

        ``app.widget(name)`` returns the outer container frame (the one that
        holds the text plus its scrollbar). Use this helper when you need the
        actual ``tk.Text`` instance, for example to bind low-level events or
        query the raw widget state.
        """
        return self._text_inner.get(name)

    def text_get(self, name: str) -> str:
        """Return the current full contents of a text widget."""
        inner = self._text_inner.get(name)
        if inner is None:
            return ""
        return str(inner.get("1.0", "end-1c"))

    def text_set(self, name: str, content: str) -> None:
        """Replace the full contents of a text widget, even when read-only."""
        inner = self._text_inner.get(name)
        if inner is None:
            return
        inner.delete("1.0", "end")
        inner.insert("1.0", content)

    def text_tag_add(self, name: str, tag: str, start: str, end: str) -> None:
        """Apply a tag to a text range, even when read-only."""
        inner = self._text_inner.get(name)
        if inner is None:
            return
        inner.tag_add(tag, start, end)

    @property
    def root(self) -> tk.Tk | None:
        """Return the root Tk window (available after run)."""
        return self._root

    def widget_kind(self, name: str) -> str | None:
        for w in self._widgets:
            if w.name == name:
                return w.kind
        return None

    def widget_specs(self, *, kind: str | None = None) -> list[WidgetSpec]:
        if kind is None:
            return list(self._widgets)
        return [w for w in self._widgets if w.kind == kind]

    def debug_layout(self) -> dict[str, Any]:
        """Collect runtime geometry/state for every registered widget.

        Useful for diagnosing clipping, minsize, and geometry-manager issues
        without needing to sprinkle ``winfo_*`` calls in user code.  Output is
        JSON-compatible so it can be logged or handed to an agent.
        """
        out: dict[str, Any] = {"title": self._title, "sections": []}
        seen_sections: dict[int, dict[str, Any]] = {}
        for spec in self._widgets:
            name = spec.name
            w = self._tk_widgets.get(name)
            if w is None:
                continue
            master = w.master
            sec_id = id(master)
            if sec_id not in seen_sections:
                seen_sections[sec_id] = {
                    "master_class": master.winfo_class(),
                    "master_geometry": master.winfo_geometry(),
                    "widgets": [],
                }
            info: dict[str, Any] = {
                "name": name,
                "kind": spec.kind,
                "class": w.winfo_class(),
                "geometry": w.winfo_geometry(),
                "reqwidth": w.winfo_reqwidth(),
                "reqheight": w.winfo_reqheight(),
                "manager": w.winfo_manager(),
                "ismapped": bool(w.winfo_ismapped()),
                "viewable": bool(w.winfo_viewable()),
            }
            try:
                mgr = w.winfo_manager()
                if mgr == "pack":
                    pi = w.pack_info()
                    info["pack_info"] = {
                        "side": pi.get("side"),
                        "fill": pi.get("fill"),
                        "expand": pi.get("expand"),
                    }
                elif mgr == "grid":
                    gi = w.grid_info()
                    info["grid_info"] = {
                        "row": gi.get("row"),
                        "column": gi.get("column"),
                        "sticky": gi.get("sticky"),
                    }
            except tk.TclError:
                pass
            seen_sections[sec_id]["widgets"].append(info)
        out["sections"] = list(seen_sections.values())
        return out

    def _spec(self, name: str) -> WidgetSpec | None:
        for w in self._widgets:
            if w.name == name:
                return w
        return None

    def apply_state(self, update: dict[str, Any]) -> None:
        self._apply_state(update)

    def _apply_initial_state(self, initial_state: dict[str, Any]) -> None:
        """Apply initial state, registering its keys as app-declared.

        ``initial_state`` is the app declaring its state schema, so its keys
        are never typo-warning candidates.
        """
        self._declared_state_keys.update(initial_state)
        self.apply_state(initial_state)

    def sync(self) -> None:
        self._sync_widgets()
        self._sync_menubar()
        self._sync_widget_states()

    def pump(self) -> None:
        """Process pending Tk events without entering mainloop."""
        if self._root is None:
            return
        try:
            while self._root.tk.dooneevent(0):
                pass
        except tk.TclError:
            return

    def run_stages(
        self,
        *,
        stages: list[str],
        key: str,
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
    ) -> None:
        """Build and run the app with state-driven stage switching.

        Unlike ``run_multiview`` this does not use a Notebook: only the
        stage named by ``state[key]`` is packed into the body at a time.
        Calling ``apply_state({key: "other_stage"})`` swaps the body.
        """
        root = self._setup_stages(
            name="__run_stages__",
            stages=stages,
            key=key,
            toplevel_widgets=toplevel_widgets,
            initial_state=initial_state,
            view_layouts=view_layouts,
            center_kinds=center_kinds,
            on_ready=on_ready,
        )
        root.mainloop()

    def run_multiview(
        self,
        *,
        views: list[str],
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
        on_tab_change: NotebookTabChange | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        tabposition: str = "nw",
    ) -> None:
        """Build and run the app in a ttk.Notebook container.

        This keeps examples close to ``app.run(layout=...)`` style while supporting
        multi-view/tab UIs.

        ``tabposition`` is forwarded to ``ttk.Notebook`` (e.g. ``"nw"`` for
        top, ``"w"`` for left, ``"e"`` for right, ``"s"`` for bottom).
        """
        root = self._setup_multiview(
            views=views,
            toplevel_widgets=toplevel_widgets,
            initial_state=initial_state,
            view_layouts=view_layouts,
            center_kinds=center_kinds,
            on_tab_change=on_tab_change,
            on_ready=on_ready,
            tabposition=tabposition,
        )
        root.mainloop()

    async def _async_run_multiview(
        self,
        *,
        views: list[str],
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
        on_tab_change: NotebookTabChange | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        tabposition: str = "nw",
    ) -> None:
        """Async variant: multiview setup + cooperative asyncio mainloop.

        Sets ``_event_loop`` before ``on_ready`` so ``app.spawn`` /
        ``@app.job`` work in multiview mode (they silently failed before).
        """
        self._event_loop = asyncio.get_running_loop()
        self._setup_multiview(
            views=views,
            toplevel_widgets=toplevel_widgets,
            initial_state=initial_state,
            view_layouts=view_layouts,
            center_kinds=center_kinds,
            on_tab_change=on_tab_change,
            on_ready=on_ready,
            tabposition=tabposition,
        )
        await self._async_mainloop()

    def _setup_multiview(
        self,
        *,
        views: list[str],
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
        on_tab_change: NotebookTabChange | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        tabposition: str = "nw",
    ) -> tk.Tk:
        """Build the Notebook UI; everything except entering a mainloop."""
        root = tk.Tk()
        root.title(self._title)
        self._configure_theme(root)
        self.set_root(root)
        self.clear_runtime()

        from nextpytk.theme import content_frame
        from nextpytk import tokens as t

        # Wrap the whole multiview in a Kizashi content frame so the page
        # margin and ground color apply consistently across tabs.
        body = content_frame(root, padding=t.SPACE[6])

        # Apply per-multiview tab position via the ttk style (Tcl
        # ``tabposition`` is not exposed on the widget in Tk 9.0/Py 3.14,
        # but the TNotebook style does accept it).
        try:
            ttk.Style(root).configure("TNotebook", tabposition=tabposition)
        except tk.TclError:
            pass

        # Fit the TNotebook.Tab width to the longest view label so app
        # developers do not need to hand-tune width per app. Without this
        # every tab collapses to the natural width of its text, which
        # makes a Notebook look ragged.
        try:
            from tkinter import font as tkfont
            style = ttk.Style(root)
            font_spec = style.lookup("TNotebook.Tab", "font")
            if font_spec and views:
                f = tkfont.Font(font=font_spec)
                max_px = max(f.measure(v) for v in views)
                avg_px = f.measure("0") or 1
                # 2-char safety margin so the label never touches the border.
                char_w = max(4, -(-max_px // avg_px) + 2)
                style.configure("TNotebook.Tab", width=char_w)
        except Exception:
            pass

        nb = ttk.Notebook(body)
        frames: dict[str, tk.Frame] = {}
        jobs_by_view: dict[str, tuple[Layout, list[Any], list[Any]]] = {}

        layouts = dict(self._view_layouts)
        if view_layouts:
            for k, v in view_layouts.items():
                if isinstance(v, list):
                    from nextpytk.layout import Layout
                    view_layouts[k] = Layout.from_list(v)
            layouts.update(view_layouts)
        unknown = sorted(set(layouts.keys()) - set(views))
        if unknown:
            raise ValueError(f"view_layouts includes unknown views: {', '.join(unknown)}")

        # Separate chrome frames for header widgets (above the notebook) and
        # status widgets (below the notebook).  The status bar is rendered by
        # ``theme.status_bar`` so it looks like a bottom bar, not a centered box.
        header_widgets: list[str] = []
        status_widgets: list[str] = []
        for name in toplevel_widgets:
            spec = self._spec(name)
            if spec is not None and getattr(spec, "role", None) == "status":
                status_widgets.append(name)
            else:
                header_widgets.append(name)

        if header_widgets or status_widgets:
            chrome = tk.Frame(body, bg=t.BG, bd=0, highlightthickness=0)
            chrome.pack(fill="x", pady=(0, t.SPACE[3]))
            self._multiview_header_container = chrome
            from nextpytk.theme import window_header
            self._multiview_header_fn = window_header
        else:
            chrome = None
            self._multiview_header_container = None
            self._multiview_header_fn = None

        if status_widgets:
            status_bar_frame = tk.Frame(body, bg=t.BG, bd=0, highlightthickness=0)
            status_bar_frame.pack(side="bottom", fill="x", pady=(t.SPACE[3], 0), padx=t.SPACE[6])
            self._multiview_status_container = status_bar_frame
        else:
            status_bar_frame = None
            self._multiview_status_container = None

        for name in header_widgets:
            self.set_widget_master(name, chrome if chrome is not None else body)
        for name in status_widgets:
            self.set_widget_master(name, status_bar_frame if status_bar_frame is not None else body)

        for view in views:
            frame = tk.Frame(nb, name=f"tabframe_{view}")
            frame.configure(bg=t.BG, bd=0, highlightthickness=0)
            frames[view] = frame
            if view in layouts:
                layout = layouts[view]
                allowed = set(self.view_widget_names(view))
                row_jobs, grid_jobs = layout.mount_frames_into(
                    self, frame, allowed_widgets=allowed)
                jobs_by_view[view] = (layout, row_jobs, grid_jobs)
            else:
                # Same inner content margin as layout-managed views.
                inner = tk.Frame(frame, bg=t.BG, bd=0, highlightthickness=0)
                inner.pack(fill="both", expand=True,
                           padx=t.SPACE[6], pady=t.SPACE[4])
                for wname in self.view_widget_names(view):
                    self.set_widget_master(wname, inner)

        self.build_widgets()

        if initial_state:
            self._apply_initial_state(initial_state)

        if chrome is not None:
            for name in header_widgets:
                w = self.widget(name)
                if w is not None:
                    w.pack(fill="x", pady=(0, t.SPACE[1]))

        nb.pack(fill="both", expand=True, pady=(t.SPACE[2], 0))

        if status_bar_frame is not None:
            for name in status_widgets:
                w = self.widget(name)
                if w is not None:
                    w_any: Any = w
                    try:
                        w_any.configure(anchor="w", font=t.font("small"),
                                        foreground=t.NEUTRAL[700])
                    except tk.TclError:
                        pass
                    w.pack(fill="x", pady=(t.SPACE[1], 0))

        for view in views:
            nb.add(frames[view], text=view)

        centered = center_kinds or set()
        for view in views:
            if view in jobs_by_view:
                layout, row_jobs, grid_jobs = jobs_by_view[view]
                layout.pack_children_for(self, row_jobs, grid_jobs)
            else:
                self.pack_view_widgets(view, center_kinds=centered, fill="x", pady=2)

        def _on_tab_changed(_event: tk.Event[tk.Misc] | None = None) -> None:
            current = nb.select()
            if not current:
                return
            view = str(nb.tab(current, "text"))
            if on_tab_change is None:
                return
            update = on_tab_change(view)
            if update:
                self.apply_state(update)

        nb.bind("<<NotebookTabChanged>>", _on_tab_changed)
        if views:
            nb.select(0)
            _on_tab_changed()

        if on_ready is not None:
            on_ready(self)

        self.draw_canvas_items()
        self.sync()
        self._set_initial_focus()
        return root

    # ── async job registration ──

    def job(
        self,
        name: str,
        *,
        description: str | None = None,
    ) -> Callable[[AsyncJob], AsyncJob]:
        """Register an async coroutine as a named job.

        Usage::

            @app.job("scan")
            async def scan():
                result = await asyncio.to_thread(blocking_io)
                return {"status": "done"}
        """
        def decorator(fn: AsyncJob) -> AsyncJob:
            self._jobs[name] = fn
            return fn
        return decorator

    def _setup_stages(
        self,
        *,
        name: str,
        stages: list[str],
        key: str,
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
    ) -> tk.Tk:
        """Build the state-driven stage UI; everything except entering mainloop."""
        self._stages[name] = {
            "stages": list(stages),
            "key": key,
            "toplevel_widgets": tuple(toplevel_widgets),
            "initial_state": dict(initial_state) if initial_state else None,
            "view_layouts": dict(view_layouts) if view_layouts else None,
            "center_kinds": set(center_kinds) if center_kinds else None,
        }
        root = tk.Tk()
        root.title(self._title)
        self._configure_theme(root)
        self.set_root(root)
        self.clear_runtime()

        from nextpytk.theme import content_frame
        from nextpytk import tokens as t

        body = content_frame(root, padding=t.SPACE[6])

        header_widgets: list[str] = []
        status_widgets: list[str] = []
        for name in toplevel_widgets:
            spec = self._spec(name)
            if spec is not None and getattr(spec, "role", None) == "status":
                status_widgets.append(name)
            else:
                header_widgets.append(name)

        if header_widgets or status_widgets:
            chrome = tk.Frame(body, bg=t.BG, bd=0, highlightthickness=0)
            chrome.pack(fill="x", pady=(0, t.SPACE[3]))
            self._multiview_header_container = chrome
        else:
            chrome = None
            self._multiview_header_container = None
        self._multiview_header_fn = None

        if status_widgets:
            status_bar_frame = tk.Frame(body, bg=t.BG, bd=0, highlightthickness=0)
            status_bar_frame.pack(side="bottom", fill="x", pady=(t.SPACE[3], 0), padx=t.SPACE[6])
            self._multiview_status_container = status_bar_frame
        else:
            status_bar_frame = None
            self._multiview_status_container = None

        for name in header_widgets:
            self.set_widget_master(name, chrome if chrome is not None else body)
        for name in status_widgets:
            self.set_widget_master(name, status_bar_frame if status_bar_frame is not None else body)

        stage_container = tk.Frame(body, bg=t.BG, bd=0, highlightthickness=0)
        stage_container.pack(fill="both", expand=True, pady=(t.SPACE[2], 0))
        self._stage_container = stage_container

        layouts = dict(self._view_layouts)
        if view_layouts:
            for k, v in view_layouts.items():
                if isinstance(v, list):
                    from nextpytk.layout import Layout
                    view_layouts[k] = Layout.from_list(v)
            layouts.update(view_layouts)
        unknown = sorted(set(layouts.keys()) - set(stages))
        if unknown:
            raise ValueError(f"view_layouts includes unknown stages: {', '.join(unknown)}")

        jobs_by_stage: dict[str, tuple[Layout, list[Any], list[Any]]] = {}
        self._stage_frames: dict[str, tk.Frame] = {}

        for stage in stages:
            frame = tk.Frame(stage_container, name=f"stageframe_{stage}", bg=t.BG, bd=0, highlightthickness=0)
            self._stage_frames[stage] = frame
            if stage in layouts:
                layout = layouts[stage]
                allowed = set(self.view_widget_names(stage))
                row_jobs, grid_jobs = layout.mount_frames_into(self, frame, allowed_widgets=allowed)
                jobs_by_stage[stage] = (layout, row_jobs, grid_jobs)
            else:
                inner = tk.Frame(frame, bg=t.BG, bd=0, highlightthickness=0)
                inner.pack(fill="both", expand=True, padx=t.SPACE[6], pady=t.SPACE[4])
                for wname in self.view_widget_names(stage):
                    self.set_widget_master(wname, inner)

        if initial_state:
            self._apply_initial_state(initial_state)

        self.build_widgets()

        if chrome is not None:
            for name in header_widgets:
                w = self.widget(name)
                if w is not None:
                    w.pack(fill="x", pady=(0, t.SPACE[1]))

        if status_bar_frame is not None:
            for name in status_widgets:
                w = self.widget(name)
                if w is not None:
                    w_any: Any = w
                    try:
                        w_any.configure(anchor="w", font=t.font("small"),
                                        foreground=t.NEUTRAL[700])
                    except tk.TclError:
                        pass
                    w.pack(fill="x", pady=(t.SPACE[1], 0))

        centered = center_kinds or set()
        for stage in stages:
            if stage in jobs_by_stage:
                layout, row_jobs, grid_jobs = jobs_by_stage[stage]
                layout.pack_children_for(self, row_jobs, grid_jobs)
            else:
                self.pack_view_widgets(stage, center_kinds=centered, fill="x", pady=2)

        active = str(self._state.get(key, stages[0] if stages else ""))
        if active not in stages:
            active = stages[0] if stages else ""
        self._render_stage(active, key=key, centered=centered)

        if on_ready is not None:
            on_ready(self)

        self.draw_canvas_items()
        self.sync()
        self._set_initial_focus()
        return root

    def _render_stage(self, stage: str, *, key: str, centered: set[str]) -> None:
        """Pack the requested stage frame and unpack the others."""
        container = self._stage_container
        if container is None:
            return
        for name, frame in self._stage_frames.items():
            if name == stage:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        self._current_stage = stage
        self._state[key] = stage

    def spawn(self, coro):
        """Schedule an async task on the running event loop.

        Raises RuntimeError if no event loop is running.
        """
        if self._event_loop is None or not self._event_loop.is_running():
            raise RuntimeError("No running event loop -- call app.run() first")
        task = asyncio.ensure_future(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _async_poll(self) -> None:
        """Poll Tk events cooperatively with asyncio."""
        if self._root is None:
            return
        try:
            while self._root.tk.dooneevent(0):
                pass
        except tk.TclError:
            return

    def stop(self) -> None:
        """Signal the async mainloop to stop gracefully."""
        self._async_stop = True

    async def _async_mainloop(self) -> None:
        """Cooperative async mainloop: Tk event processing + asyncio scheduler.

        Terminates when the window is closed (via WM_DELETE_WINDOW)
        or application sets ``self._async_stop = True``.
        """
        root = self._root
        if root is None:
            return

        self._async_stop = False

        def _on_close():
            self._async_stop = True
            root.destroy()
        root.protocol("WM_DELETE_WINDOW", _on_close)

        try:
            while not self._async_stop:
                try:
                    root.update()
                except tk.TclError:
                    break
                await asyncio.sleep(0.01)
        finally:
            self._async_stop = True

    def draw_canvas_items(self) -> None:
        """Draw configured canvas items for all registered canvas widgets."""
        for spec in self.widget_specs(kind="canvas"):
            w = self.widget(spec.name)
            if w is None:
                continue
            for item in spec.extras.get("items", []):
                if not isinstance(item, tuple) or len(item) < 2:
                    continue
                kind = item[0]
                if not isinstance(kind, str):
                    continue
                method = getattr(w, f"create_{kind}", None)
                if method is None:
                    continue
                *args, kwargs = item[1:]
                if isinstance(kwargs, dict):
                    method(*args, **kwargs)
                else:
                    method(*(item[1:]))

    def pack_view_widgets(
        self,
        view_name: str,
        *,
        center_kinds: set[str] | None = None,
        fill: FillLike = "x",
        pady: int | None = None,
    ) -> None:
        """Pack all widgets registered in a named view."""
        if pady is None:
            pady = t.SPACE[1]
        centered = center_kinds or set()
        for wname in self.view_widget_names(view_name):
            w = self.widget(wname)
            if w is None:
                continue
            kind = self.widget_kind(wname)
            if kind in centered:
                w.pack(pady=pady)
            else:
                w.pack(fill=fill, pady=pady)

    # ── widget registration decorators ──

    def label(
        self,
        name: str,
        **options: Unpack[LabelOptions],
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a label. Decorated function returns text or state dict.

        ``width``: fixed character width (ttk.Label) so long text does not
        expand the window. ``takefocus``: Tab key traversal (``0`` / ``1`` /
        ``""`` or bool).
        """
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
            self._add_spec(WidgetSpec(
                name=name, kind="label",
                role=options.get("role"),
                description=options.get("description"),
                on_update=fn,
                extras=self._widget_extras(extras, takefocus=options.get("takefocus")),
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
        **options: Unpack[BindOptions],
    ) -> Callable[[BindCallback], BindCallback]:
        """Register a global key binding.

        ``sequence``: Tk event sequence (e.g. ``"<Control-s>"``, ``"<Alt-Down>"``).
        ``label``: human-readable shortcut label (e.g. ``"Ctrl+S"``).
          Displayed in button text and exposed in ``schema()`` output.

        The decorated function receives the current state dict and returns
        a state update dict (same signature as button callbacks).

        Example::

            @app.bind("save", sequence="<Control-s>", label="Ctrl+S",
                      description="Save the right pane")
            def save_binding(state: dict[str, Any]) -> dict[str, Any]:
                return {"status_bar": "Saved"}

        Bindings are applied globally via ``root.bind_all()`` during
        ``_build_widgets()``.  When a matching button widget exists
        (same ``name``), the shortcut label is appended to the button text
        automatically.
        """
        sequence = options["sequence"]
        label = options.get("label", "")
        description = options.get("description")
        def decorator(fn: BindCallback) -> BindCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="bind", label_text=label,
                role="shortcut", description=description,
                on_click=lambda state: fn(state),
                bindings=[(sequence, label)],
            ))
            return fn
        return decorator

    def message(
        self,
        name: str,
        **options: Unpack[MessageOptions],
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a message widget with wrap support.

        ``width``: initial wrap width in pixels. If omitted and ``auto_width=True``,
        width follows parent container resize.
        """
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
                extras=self._widget_extras(extras, takefocus=options.get("takefocus")),
            ))
            return fn
        return decorator

    @staticmethod
    def _menubar_item_is_separator(item: Any) -> bool:
        """Return True if the item represents a menu separator."""
        return isinstance(item, str) and item == "---"

    @staticmethod
    def _menubar_item_enabled(
        item: dict[str, Any], values: dict[str, Any]
    ) -> bool:
        """Evaluate an item's enabled_if callable, if present."""
        enabled_if = item.get("enabled_if")
        if enabled_if is None:
            return True
        try:
            return bool(enabled_if(values))
        except Exception:
            return True

    @staticmethod
    def _menubar_items(
        spec: WidgetSpec,
    ) -> list[dict[str, Any]]:
        """Return the resolved list of menubar item dicts from the spec."""
        items = spec.extras.get("items", [])
        return [dict(i) if isinstance(i, dict) else {"separator": True} for i in items]

    def _build_menubar_submenu(
        self,
        parent: tk.Menu,
        items: list[dict[str, Any]],
        parent_key: str | int = "",
    ) -> list[tk.Menu | None]:
        """Populate a tk.Menu with commands, separators and nested cascades.

        Returns a flat list parallel to ``items`` with a Menu reference for
        cascade entries and None for commands/separators, so callers can
        recurse without relying on platform-specific Tk options.
        """
        submenus: list[tk.Menu | None] = []
        for item in items:
            if item.get("separator"):
                parent.add_separator()
                submenus.append(None)
                continue
            label = str(item.get("label", ""))
            sub_items = item.get("items")
            if isinstance(sub_items, (list, tuple)) and sub_items:
                submenu = tk.Menu(parent, tearoff=0)
                parent.add_cascade(label=label, menu=submenu)
                key = id(submenu)
                submenus.append(submenu)
                child_submenus = self._build_menubar_submenu(
                    submenu,
                    [
                        dict(si) if isinstance(si, dict) else {"separator": True}
                        for si in sub_items
                    ],
                    parent_key=key,
                )
                self._menubar_submenus[key] = child_submenus
                continue
            command_name = str(item.get("command", ""))
            parent.add_command(
                label=label,
                command=lambda n=command_name, l=label: self._on_menubar_command(n, l),
            )
            submenus.append(None)
        if parent_key:
            self._menubar_submenus[parent_key] = submenus
        return submenus

    def _build_menubar(self, spec: WidgetSpec, _master: tk.Misc) -> None:
        """Create a top-level menubar and attach it to the root window."""
        root = self._root
        if root is None:
            return
        menubar = tk.Menu(root, tearoff=0)
        self._tk_widgets[spec.name] = menubar
        root.config(menu=menubar)
        # Resolve the initial item list so subsequent sync() calls can detect
        # dynamic structural changes without rebuilding on every state update.
        initial_items: list[Any] = []
        if spec.on_update is not None:
            result = self._dispatch(spec.name, spec.on_update)
            if isinstance(result, list):
                initial_items = result
            elif isinstance(result, dict):
                initial_items = result.get(spec.name, [])
        extras_items: list[Any] = []
        for item in initial_items:
            if isinstance(item, dict):
                extras_items.append(dict(item))
            else:
                extras_items.append({"separator": True})
        spec.extras["items"] = extras_items
        self._menubar_submenus[spec.name] = self._build_menubar_submenu(
            menubar, extras_items, parent_key=spec.name
        )

    def _on_menubar_command(self, command_name: str, label: str) -> None:
        """Invoke the registered handler for a menubar item."""
        spec = self._spec(command_name)
        if spec is None or spec.on_click is None:
            return
        values = self._entry_values_dict()
        self._state[command_name] = label
        result = self._dispatch(command_name, spec.on_click, values)
        if isinstance(result, dict) and result:
            self._apply_state(result)

    def _sync_menubar_states(self) -> None:
        """Update menubar item enabled/disabled state from enabled_if."""
        values = {**self._state, **self._entry_values_dict()}
        for spec in self.widget_specs(kind="menubar"):
            menubar = self._tk_widgets.get(spec.name)
            if not isinstance(menubar, tk.Menu):
                continue
            submenus = self._menubar_submenus.get(spec.name, [])
            self._sync_menubar_menu_states(
                menubar, self._menubar_items(spec), values, submenus
            )

    def _sync_menubar_menu_states(
        self,
        menu: tk.Menu,
        items: list[dict[str, Any]],
        values: dict[str, Any],
        submenus: list[tk.Menu | None],
    ) -> None:
        """Recursively update enabled_if states for a tk.Menu and its submenus."""
        idx = 0
        for item in items:
            if item.get("separator"):
                idx += 1
                continue
            sub_items = item.get("items")
            if isinstance(sub_items, (list, tuple)) and sub_items:
                sub = submenus[idx] if idx < len(submenus) else None
                if isinstance(sub, tk.Menu):
                    child_submenus = self._menubar_submenus.get(id(sub), [])
                    self._sync_menubar_menu_states(
                        sub,
                        [
                            dict(si) if isinstance(si, dict) else {"separator": True}
                            for si in sub_items
                        ],
                        values,
                        child_submenus,
                    )
                idx += 1
                continue
            ok = self._menubar_item_enabled(item, values)
            try:
                menu.entryconfig(idx, state="normal" if ok else "disabled")
            except tk.TclError:
                pass
            idx += 1

    def _sync_menubar(self) -> None:
        """Refresh menubar item labels and commands from the decorator.

        The menu is only rebuilt when the decorator returns a different item
        list; otherwise existing Tk widgets are preserved so submenu references
        and platform-specific menu bindings remain valid.
        """
        for spec in self.widget_specs(kind="menubar"):
            menubar = self._tk_widgets.get(spec.name)
            if not isinstance(menubar, tk.Menu):
                continue
            if spec.on_update is None:
                continue
            result = self._dispatch(spec.name, spec.on_update)
            items: list[Any] = []
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                items = result.get(spec.name, [])
            if not isinstance(items, list):
                continue
            extras_items: list[Any] = []
            for item in items:
                if isinstance(item, dict):
                    extras_items.append(dict(item))
                else:
                    extras_items.append({"separator": True})
            existing = spec.extras.get("items", [])
            if not self._menubar_items_equal(existing, extras_items):
                # Clear and rebuild the menubar to reflect dynamic item changes.
                menubar.delete(0, "end")
                spec.extras["items"] = extras_items
                self._menubar_submenus[spec.name] = self._build_menubar_submenu(
                    menubar, extras_items, parent_key=spec.name
                )
            else:
                spec.extras["items"] = extras_items
        self._sync_menubar_states()

    @staticmethod
    def _menubar_items_equal(a: list[Any], b: list[Any]) -> bool:
        """Return True when two menubar item lists describe the same structure.

        Only label, command and nested structure are compared; ``enabled_if``
        callables are intentionally ignored so that state-driven enablement
        does not force a full menu rebuild.
        """
        if len(a) != len(b):
            return False
        for ai, bi in zip(a, b):
            if isinstance(ai, dict) != isinstance(bi, dict):
                return False
            if isinstance(ai, dict):
                if not isinstance(bi, dict):
                    return False
                if ai.get("label") != bi.get("label"):
                    return False
                if ai.get("command") != bi.get("command"):
                    return False
                sub_a = ai.get("items")
                sub_b = bi.get("items")
                if isinstance(sub_a, (list, tuple)) != isinstance(sub_b, (list, tuple)):
                    return False
                if isinstance(sub_a, (list, tuple)) and isinstance(sub_b, (list, tuple)):
                    if not TkApp._menubar_items_equal(list(sub_a), list(sub_b)):
                        return False
            elif ai != bi:
                return False
        return True

    def menubar(
        self,
        name: str,
        **options: Unpack[MenubarOptions],
    ) -> Callable[[MenubarCallback], MenubarCallback]:
        """Register a top-level menubar.

        The decorated function returns a list of item dicts and separator
        strings. Top-level items with ``items`` become cascades (submenus);
        items with ``command`` invoke the registered handler name.
        Each command item may contain ``enabled_if`` with the same Callable
        signature used by buttons.

        Example::

            @app.menubar("menu")
            def menu_bar():
                return [
                    {"label": "File", "items": [
                        {"label": "New", "command": "m_new"},
                        {"label": "Save", "command": "m_save",
                         "enabled_if": lambda vals: bool(vals.get("dirty"))},
                        "---",
                        {"label": "Exit", "command": "m_exit"},
                    ]},
                ]

            @app.button("m_new")
            def m_new(vals): return {"msg": "New"}
        """
        def decorator(fn: MenubarCallback) -> MenubarCallback:
            items = options.get("items")
            extras: dict[str, Any] = {}
            if items is not None:
                extras["items"] = list(items)
            self._add_spec(WidgetSpec(
                name=name, kind="menubar",
                description=options.get("description"),
                on_update=fn,
                extras=extras,
            ))
            return fn
        return decorator

    def button(
        self,
        name: str,
        **options: Unpack[ButtonOptions],
    ) -> Callable[[ButtonCallback], ButtonCallback]:
        """Register a button. Callback receives entry values dict → returns state dict.

        ``label``: button text.
        ``state``: initial widget state (``"normal"`` / ``"disabled"``).
        ``primary``: use the filled accent style (``Primary.TButton``); otherwise
        the outlined neutral style (``Secondary.TButton``).
        When ``enabled_if`` is set, it takes over after the first sync.
        """
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
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def entry(
        self,
        name: str,
        **options: Unpack[EntryOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register an entry. Callback receives value string → returns state dict.

        ``placeholder``: hint text shown when empty.
        ``show``: set ``"*"`` for password entry.
        ``width``: character width.
        ``state``: initial widget state (``"normal"`` / ``"disabled"``).
        ``font``: optional ``(family, size[, weight])`` tuple.
        ``padding``: internal padding override; integer or tuple to increase
        visual height (ttk.Entry does not support ``height`` directly).
        """
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
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def checkbutton(
        self,
        name: str,
        **options: Unpack[CheckbuttonOptions],
    ) -> Callable[[BoolCallback], BoolCallback]:
        """Register a checkbutton. Callback receives bool → returns state dict.

        ``state[key]`` is ``"1"`` or ``"0"``. Key defaults to name.
        """
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
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def radiobutton(
        self,
        name: str,
        **options: Unpack[RadiobuttonOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a radiobutton. Callback receives selected value → returns state dict.

        All radiobuttons sharing the same *group* write to ``state[group]``.
        """
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
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def text(
        self,
        name: str,
        **options: Unpack[TextOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a multiline text widget. Callback receives full content → returns state dict.

        ``tab_inserts``: when True, Tab inserts a tab character (default tk
        behavior). When False (default), Tab moves focus to the next widget
        and the user can use Ctrl+Tab / Ctrl+I to insert a literal tab
        (WCAG 2.1.1 Keyboard, 2.4.3 Focus Order).
        """
        width = options.get("width", 50)
        height = options.get("height", 8)
        description = options.get("description")
        state = options.get("state", "normal")
        tab_inserts = options.get("tab_inserts", False)
        readonly = options.get("readonly", False)
        tags = options.get("tags")
        sync_yscroll_with = options.get("sync_yscroll_with")
        takefocus = options.get("takefocus", True)
        font = options.get("font")
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
            self._add_spec(WidgetSpec(
                name=name, kind="text", description=description,
                on_update=fn,
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def scale(
        self,
        name: str,
        **options: Unpack[ScaleOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a scale slider. Callback receives current value → returns state dict.

        ``state[key]`` holds the int value. Key defaults to name.
        """
        actual_key = options.get("key") or name
        from_ = options.get("from_", 0)
        to = options.get("to", 100)
        orient = options.get("orient", "horizontal")
        description = options.get("description")
        takefocus = options.get("takefocus")
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="scale", description=description,
                on_update=fn,
                extras=self._widget_extras({
                    "state_key": actual_key, "from": from_,
                    "to": to, "orient": orient,
                }, takefocus=takefocus),
            ))
            return fn
        return decorator

    def spinbox(
        self,
        name: str,
        **options: Unpack[SpinboxOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a spinbox. Callback receives current value → returns state dict.

        ``state[key]`` holds the string value. Key defaults to name.
        ``width``: character width of the entry field.
        """
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
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def combobox(
        self,
        name: str,
        **options: Unpack[ComboboxOptions],
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a ``ttk.Combobox``. Callback receives selected value → returns state dict.

        ``values``: list of selectable strings.
        ``values_key``: state key for dynamic values. When omitted, ``values=`` is
        used as a static list. With ``values_key``,
        ``apply_state({values_key: [...]})`` refreshes the dropdown choices while
        keeping the selected string in ``state[key]``.
        ``state[key]`` holds the current string value. Key defaults to name.
        ``readonly``: when True, the user can only pick from ``values``.
        ``font``: optional ``(family, size[, weight])`` tuple.
        ``padding``: internal padding override; integer or tuple.

        Example::

            @app.combobox("folder", values_key="folder_values")
            def on_folder(value: str) -> dict[str, str]:
                return {}

            app.apply_state({"folder_values": ["INBOX", "Sent", "Drafts"]})
        """
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
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def listbox(
        self,
        name: str,
        **options: Unpack[ListboxOptions],
    ) -> Callable[[ListboxSelectCallback], ListboxSelectCallback]:
        """Register a listbox. Callback receives selected index → returns state dict.

        ``state[name]`` holds the selected item index, or ``-1`` when nothing
        is selected. This matches the behavior of ``treeview`` callbacks and
        avoids ambiguity caused by duplicate display strings.
        ``enabled_if``: disables selection when False (sets selectmode="none").
        ``items_key``: state key for dynamic items. When omitted, ``items=`` is
        used as a static list. With ``items_key``, ``apply_state({items_key: [...]})``
        refreshes the listbox contents while keeping selection state in
        ``state[name]``.
        ``events``: widget-level event bindings. Each handler receives the
        current state dict and returns a state update dict (same signature as
        button callbacks). Use ``nextpytk.types.EventSeq`` constants for
        common sequences such as ``EventSeq.RETURN`` or
        ``EventSeq.PRIMARY_DOUBLE_CLICK`` for an a11y-aware double-click.

        Example::

            @app.listbox(
                "results",
                items_key="results_items",
                selectmode=SelectMode.BROWSE,
                events={
                    EventSeq.RETURN: lambda state: open_child(),
                    EventSeq.PRIMARY_DOUBLE_CLICK: lambda state: open_child(),
                    EventSeq.BACKSPACE: lambda state: go_parent(),
                },
            )
            def on_results_select(idx: int) -> dict[str, Any]:
                ...

            app.apply_state({"results_items": ["a", "b", "c"]})
        """
        items = options.get("items")
        items_key = options.get("items_key")
        selectmode = options.get("selectmode", "browse")
        height = options.get("height")
        description = options.get("description")
        enabled_if = options.get("enabled_if")
        takefocus = options.get("takefocus")
        events = options.get("events")
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
                extras=self._widget_extras(extras, takefocus=takefocus),
                enabled_if=enabled_if,
            ))
            return fn
        return decorator

    def treeview(
        self,
        name: str,
        **options: Unpack[TreeviewOptions],
    ) -> Callable[[TreeviewSelectCallback], TreeviewSelectCallback]:
        """Register a flat ``ttk.Treeview`` table (``show="headings"``).

        ``columns``: list of ``(id, heading)`` / ``(id, heading, width)``
        or ``(id, heading, width, anchor)`` tuples, or dicts with
        ``id``, ``heading``, ``width``, ``anchor``, ``stretch``.

        ``state[rows_key]``: list of row value tuples (column order).
        ``rows_key`` defaults to ``"{name}_rows"``.

        ``state[name]``: selected row index (``int``, ``-1`` if none).

        ``activate``: optional double-click handler (same signature as select).
        """
        columns = options["columns"]
        rows_key = options.get("rows_key")
        selectmode = options.get("selectmode", "browse")
        height = options.get("height", 8)
        description = options.get("description")
        activate = options.get("activate")
        takefocus = options.get("takefocus")
        col_ids, col_configs = _normalize_treeview_columns(columns)
        actual_rows_key = rows_key or f"{name}_rows"

        def decorator(fn: TreeviewSelectCallback) -> TreeviewSelectCallback:
            extras: dict[str, Any] = {
                "column_ids": col_ids,
                "column_configs": col_configs,
                "rows_key": actual_rows_key,
                "selectmode": selectmode,
                "height": height,
            }
            self._add_spec(WidgetSpec(
                name=name, kind="treeview", description=description,
                on_update=fn, on_click=activate,
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def paned(
        self,
        name: str,
        **options: Unpack[PanedOptions],
    ) -> None:
        """Register a ``ttk.Panedwindow`` with named pane frames.

        Register child widgets inside each pane with::

            with app.pane("left"):
                @app.message("left_body")
                def left_body(): ...

        ``panes``: pane ids (unique in the app). ``weights``: relative
        sash weights passed to ``Panedwindow.add(..., weight=)``.

        ``sashwidth``: best-effort; ``ttk.Panedwindow`` often ignores it.

        Per-pane ``minsizes`` / ``weights`` for layout: use
        ``Layout.paned(name, minsizes=(...), weights=(...))`` — when any
        ``minsize > 0``, ``tk.PanedWindow`` is used automatically.

        Only the paned widget belongs in ``Layout``; pane children are packed
        inside their pane frame (``with app.pane(...)``).
        """
        panes = options["panes"]
        orient = options.get("orient", "horizontal")
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
        """Register a ``ttk.Progressbar`` driven by app state.

        ``state[key]``: numeric value ``0 .. maximum`` (determinate).
        ``state["{name}_running"]``: when ``True``, runs indeterminate
        animation (``start()``); when ``False``, ``stop()`` and restore mode.

        ``key`` defaults to ``name``. Update via ``apply_state`` from buttons
        or ``app.spawn`` / ``@app.job`` async tasks.
        """
        actual_key = options.get("key") or name
        maximum = options.get("maximum", 100.0)
        mode = options.get("mode", "determinate")
        length = options.get("length", 200)
        orient = options.get("orient", "horizontal")
        description = options.get("description")
        self._add_spec(WidgetSpec(
            name=name, kind="progressbar", description=description,
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
        """Register a canvas (display only).

        ``items``: list of ``(kind, *args, kwargs)`` to draw via ``create_{kind}``.
        """
        width = options.get("width", 300)
        height = options.get("height", 200)
        bg = options.get("bg", "#f0f0f0")
        description = options.get("description")
        items = options.get("items")
        takefocus = options.get("takefocus")
        def decorator(fn: Callable[[], None] | None = None) -> Callable[[], None]:
            extras: dict[str, Any] = {"width": width, "height": height, "bg": bg}
            if items:
                extras["items"] = items
            self._add_spec(WidgetSpec(
                name=name, kind="canvas", description=description,
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn  # type: ignore[return-value]
        return decorator
    # ── state management ──

    def _apply_state(self, update: dict[str, Any]) -> None:
        if not isinstance(update, dict):
            raise TypeError(
                f"apply_state expects a dict, got {type(update).__name__}"
            )
        self._apply_state_dict(update, full=True)

    def _apply_state_dict(self, update: dict[str, Any], *, full: bool) -> None:
        """Merge *update* into state and refresh affected widgets."""
        self._warn_unknown_state_keys(update)  # before merge: existing keys are treated as known

        # Detect stage-key changes before merging so we can rerender the body.
        # Reject unknown stage values; they are silently ignored.
        stage_change: tuple[str, str, set[str]] | None = None
        update_to_apply = dict(update)
        if self._current_stage is not None and self._stage_container is not None:
            for cfg in self._stages.values():
                stage_key = cfg["key"]
                if stage_key not in update_to_apply:
                    continue
                new_stage = str(update_to_apply[stage_key])
                valid_stages = set(self._stage_frames.keys())
                if new_stage in valid_stages:
                    if new_stage != self._state.get(stage_key):
                        stage_change = (stage_key, new_stage, cfg.get("center_kinds") or set())
                else:
                    update_to_apply.pop(stage_key, None)

        self._state.update(update_to_apply)
        for key, val in update_to_apply.items():
            var = self._tk_vars.get(key)
            if var is None:
                continue
            s = "" if val is None else str(val)
            var.set(s)
            w = self._tk_widgets.get(key)
            if isinstance(w, (tk.Entry, ttk.Entry)):
                self._apply_entry_value_after_state(key, w, var, s)
        if full:
            self._sync_widgets()
        else:
            self._sync_widgets_for_keys(update_to_apply)
        if self._treeview_update_touches_rows(update_to_apply):
            self._sync_treeviews(force=True)
        elif full and self._treeview_update_touches_selection(update_to_apply):
            self._sync_treeview_selections()
        if self._listbox_update_touches_items(update_to_apply):
            self._sync_listbox_items_for_specs(touched_keys=set(update_to_apply.keys()))
        if self._combobox_update_touches_values(update_to_apply):
            self._sync_combobox_values_for_specs(touched_keys=set(update_to_apply.keys()))
        # Update menubar regardless of full/partial so enabled_if reacts to
        # any state change (e.g. dirty flag toggled by entry or button).
        self._sync_menubar()
        self._sync_menubar_states()
        self._sync_widget_states()

        if stage_change is not None:
            key, new_stage, centered = stage_change
            self._render_stage(new_stage, key=key, centered=centered)
            # Keep state in sync with the rendered stage.
            self._state[key] = new_stage

    def _known_state_keys(self) -> set[str]:
        """Return the set of state keys that have meaning in the app."""
        keys: set[str] = set()
        for spec in self._widgets:
            if spec.kind == "checkbutton":
                keys.add(str(spec.extras.get("state_key", spec.name)))
            elif spec.kind == "radiobutton":
                keys.add(str(spec.extras.get("group_key", "radio")))
            elif spec.kind == "scale":
                keys.add(str(spec.extras.get("state_key", spec.name)))
            elif spec.kind == "spinbox":
                keys.add(str(spec.extras.get("state_key", spec.name)))
            elif spec.kind == "treeview":
                keys.add(str(spec.extras.get("rows_key", f"{spec.name}_rows")))
                keys.add(spec.name)
            elif spec.kind == "listbox":
                keys.add(str(spec.extras.get("items_key", f"{spec.name}_items")))
                keys.add(spec.name)
            elif spec.kind == "progressbar":
                keys.add(str(spec.extras.get("state_key", spec.name)))
                keys.add(f"{spec.name}_running")
                keys.add(f"{spec.name}_mode")
            elif spec.kind == "combobox":
                keys.add(str(spec.extras.get("values_key", f"{spec.name}_values")))
                keys.add(str(spec.extras.get("state_key", spec.name)))
            elif spec.kind in ("label", "status", "message", "entry", "text",
                               "listbox", "button", "bind"):
                keys.add(spec.name)
        return keys

    # Only near-misses of a known key are reported as typos. The state dict
    # is open by design: app-defined keys such as "tab" are legitimate and
    # must not warn.
    _TYPO_DISTANCE = 2

    def _warn_unknown_state_keys(self, update: dict[str, Any]) -> None:
        """Warn when a state key looks like a typo of a known key.

        Helps catch ``{"mgs": ...}`` instead of ``{"msg": ...}``. Keys that
        are declared via ``initial_state``, already present in the state
        dict, or not close to any known key are treated as intentional
        app-defined state. Each suspicious key is reported once.
        """
        if not self._widgets:
            return
        known = self._known_state_keys()
        if not known:
            return
        suspects: list[str] = []
        for key in update.keys():
            if (key in known or key in self._declared_state_keys
                    or key in self._state or key in self._warned_state_keys):
                continue
            best = min(known, key=lambda k: _levenshtein(k, key))
            d = _levenshtein(best, key)
            if not (0 < d <= self._TYPO_DISTANCE and d < len(key)):
                continue
            self._warned_state_keys.add(key)
            suspects.append(key)
            print(
                f"nextpytk: callback returned unknown state key {key!r}."
                f" Did you mean {best!r}?",
                file=sys.stderr,
            )
        if suspects and self._debug:
            raise KeyError(f"unknown state key(s): {suspects}")

    def _entry_values_dict(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for ws in self._widgets:
            if ws.kind == "entry":
                values[ws.name] = self._entry_effective_value(ws.name)
        return values

    def _sync_widget_states(self) -> None:
        if not self._tk_widgets:
            return
        values = self._entry_values_dict()
        for spec in self._widgets:
            if spec.enabled_if is None:
                continue
            tk_w = self._tk_widgets.get(spec.name)
            if tk_w is None:
                continue
            try:
                ok = bool(spec.enabled_if(values))
            except Exception:
                ok = True
            if spec.kind == "button" and isinstance(tk_w, (tk.Button, ttk.Button)):
                tk_w.configure(state="normal" if ok else "disabled")
            elif spec.kind == "listbox" and isinstance(tk_w, tk.Listbox):
                # selectmode="none" (not state="disabled"): a disabled Listbox
                # silently ignores programmatic delete/insert, so background
                # jobs could never update the list. selectmode only blocks
                # user selection; content updates, scrolling and screen-reader
                # access keep working.
                if ok:
                    orig_sm = str(spec.extras.get("selectmode", "browse"))
                    tk_w.configure(selectmode=orig_sm)
                else:
                    tk_w.selection_clear(0, "end")
                    tk_w.configure(selectmode="none")

        # Update menubar item states after per-widget states.
        self._sync_menubar_states()

        # Emit a11y state change for checkbutton / radiobutton so NVDA
        # announces toggles without polling.
        for spec in self._widgets:
            if spec.kind in ("checkbutton", "radiobutton"):
                self._emit_a11y_state_change(spec)

    def _entry_spec(self, name: str) -> WidgetSpec | None:
        for w in self._widgets:
            if w.name == name and w.kind == "entry":
                return w
        return None

    def _entry_effective_value(self, name: str) -> str:
        w = self._tk_widgets.get(name)
        var = self._tk_vars.get(name)
        if var is None or not isinstance(w, (tk.Entry, ttk.Entry)):
            return ""
        spec = self._entry_spec(name)
        if spec is not None and spec.placeholder_as_hint:
            if getattr(w, "_nextpytk_ph_active", False):
                return ""
            ph = getattr(w, "_nextpytk_placeholder", "") or ""
            if ph and var.get() == ph:
                return ""
        return var.get()

    def _entry_focus_in(self, name: str) -> None:
        try:
            w = self._tk_widgets.get(name)
            var = self._tk_vars.get(name)
            if var is None or not isinstance(w, (tk.Entry, ttk.Entry)):
                return
            spec = self._entry_spec(name)
            if spec is None or not spec.placeholder_as_hint:
                return
            ph = getattr(w, "_nextpytk_placeholder", "") or ""
            if not ph:
                return
            if getattr(w, "_nextpytk_ph_active", False) or var.get() == ph:
                var.set("")
                setattr(w, "_nextpytk_ph_active", False)
                try:
                    w.configure(foreground=getattr(w, "_nextpytk_fg_normal",
                                                   w.cget("foreground")))
                except Exception:
                    pass
        finally:
            self._sync_widget_states()

    def _entry_focus_out(self, name: str) -> None:
        try:
            w = self._tk_widgets.get(name)
            var = self._tk_vars.get(name)
            if var is None or not isinstance(w, (tk.Entry, ttk.Entry)):
                return
            spec = self._entry_spec(name)
            if spec is None or not spec.placeholder_as_hint:
                return
            ph = getattr(w, "_nextpytk_placeholder", "") or ""
            if not ph:
                return
            if not var.get().strip():
                var.set(ph)
                setattr(w, "_nextpytk_ph_active", True)
                try:
                    w.configure(foreground=PLACEHOLDER_FG)
                except Exception:
                    pass
        finally:
            self._sync_widget_states()

    def _apply_entry_value_after_state(self, name: str, w: tk.Entry | ttk.Entry,
                                        var: tk.Variable, s: str) -> None:
        spec = self._entry_spec(name)
        if spec is None or not spec.placeholder_as_hint:
            setattr(w, "_nextpytk_ph_active", False)
            try:
                w.configure(foreground=getattr(w, "_nextpytk_fg_normal",
                                                w.cget("foreground")))
            except Exception:
                pass
            return
        ph = getattr(w, "_nextpytk_placeholder", "") or ""
        try:
            fg0 = getattr(w, "_nextpytk_fg_normal", w.cget("foreground"))
        except Exception:
            fg0 = getattr(w, "_nextpytk_fg_normal", None)
        if not ph:
            setattr(w, "_nextpytk_ph_active", False)
            try:
                if fg0 is not None:
                    w.configure(foreground=fg0)
            except Exception:
                pass
            return
        if s.strip():
            setattr(w, "_nextpytk_ph_active", False)
            try:
                if fg0 is not None:
                    w.configure(foreground=fg0)
            except Exception:
                pass
            return
        setattr(w, "_nextpytk_ph_active", False)
        try:
            if fg0 is not None:
                w.configure(foreground=fg0)
        except Exception:
            pass
        focus = w.focus_get()
        if focus is not None and str(focus) == str(w):
            return
        var.set(ph)
        setattr(w, "_nextpytk_ph_active", True)
        try:
            w.configure(foreground=PLACEHOLDER_FG)
        except Exception:
            pass

    def _bind_message_auto_width(self, w: tk.Message, master: tk.Misc,
                                 *, padding: int = 16, min_width: int = 120) -> None:
        def _update_width(evt: tk.Event[tk.Misc] | None = None) -> None:
            width = master.winfo_width()
            if evt is not None:
                width = evt.width
            target = max(min_width, width - padding)
            try:
                w.configure(width=target)
            except Exception:
                pass
        master.bind("<Configure>", _update_width, add="+")
        w.after_idle(_update_width)

    def _sync_widgets(self) -> None:
        """Push state to label, text, and listbox widgets."""
        for spec in self._widgets:
            if spec.kind in ("label", "status", "message"):
                tk_w = self._tk_widgets.get(spec.name)
                if tk_w is None:
                    continue
                value = self._state.get(spec.name, "")
                if spec.name not in self._state and spec.on_update is not None:
                    result = self._dispatch(spec.name, spec.on_update)
                    if isinstance(result, str):
                        value = result
                    elif isinstance(result, dict):
                        value = result.get(spec.name, value)
                tk_w.configure(text=str(value))  # type: ignore[call-arg]
            elif spec.kind == "text":
                self._sync_text_widget(spec)
            elif spec.kind == "listbox" and spec.extras.get("items_key") is not None:
                self._sync_listbox_items(spec)
            elif spec.kind == "combobox" and spec.extras.get("values_key") is not None:
                self._sync_combobox_values(spec)

    def _sync_text_widget(self, spec: WidgetSpec) -> None:
        """Update a text widget from state if the content changed."""
        if spec.name not in self._state:
            return
        inner = self._text_inner.get(spec.name)
        if inner is None:
            return
        value = self._state.get(spec.name, "")
        current = inner.get("1.0", "end-1c")
        target = "" if value is None else str(value)
        if current == target:
            return
        # nextpytk's readonly=True does NOT set the tk state to "disabled";
        # it keeps state="normal" and swallows edit events via key bindings.
        # The branch below is defensive: it allows programmatic updates to
        # work if the user has manually disabled the widget via text_widget().
        previous_state = inner.cget("state")
        if previous_state == "disabled":
            inner.configure(state="normal")
        inner.delete("1.0", "end")
        inner.insert("1.0", target)
        if previous_state == "disabled":
            inner.configure(state="disabled")

    def _treeview_rows(self, spec: WidgetSpec) -> list[Any]:
        rows_key = spec.extras.get("rows_key", f"{spec.name}_rows")
        rows = self._state.get(rows_key, spec.extras.get("rows", []))
        return rows if isinstance(rows, list) else []

    @staticmethod
    def _treeview_rows_signature(rows: list[Any]) -> tuple[Any, ...]:
        parts: list[Any] = []
        for row in rows:
            if isinstance(row, dict):
                parts.append(tuple(sorted(row.items())))
            elif isinstance(row, (list, tuple)):
                parts.append(tuple(row))
            else:
                parts.append(str(row))
        return tuple(parts)

    def _treeview_update_touches_rows(self, update: dict[str, Any]) -> bool:
        for spec in self._widgets:
            if spec.kind != "treeview":
                continue
            rows_key = spec.extras.get("rows_key", f"{spec.name}_rows")
            if rows_key in update:
                return True
        return False

    def _treeview_update_touches_selection(self, update: dict[str, Any]) -> bool:
        """True when *update* carries a treeview selection index (not row data)."""
        for spec in self._widgets:
            if spec.kind == "treeview" and spec.name in update:
                return True
        return False

    def _sync_widgets_for_keys(self, update: dict[str, Any]) -> None:
        """Update only label/status/message/text widgets named in *update*."""
        for spec in self._widgets:
            if spec.kind in ("label", "status", "message"):
                if spec.name not in update:
                    continue
                tk_w = self._tk_widgets.get(spec.name)
                if tk_w is None:
                    continue
                tk_w.configure(text=str(update[spec.name]))  # type: ignore[call-arg]
            elif spec.kind == "text" and spec.name in update:
                self._sync_text_widget(spec)

    def _listbox_items(self, spec: WidgetSpec) -> list[str]:
        items_key = spec.extras.get("items_key")
        if items_key is not None:
            items = self._state.get(items_key, [])
        else:
            items = spec.extras.get("items", [])
        return [str(item) for item in items] if isinstance(items, list) else []

    def _listbox_update_touches_items(self, update: dict[str, Any]) -> bool:
        for spec in self._widgets:
            if spec.kind != "listbox":
                continue
            items_key = spec.extras.get("items_key", f"{spec.name}_items")
            if items_key in update:
                return True
        return False

    def _sync_listbox_items(self, spec: WidgetSpec) -> None:
        w = self._tk_widgets.get(spec.name)
        if w is None or not isinstance(w, tk.Listbox):
            return
        items = self._listbox_items(spec)
        w.delete(0, "end")
        for item in items:
            w.insert("end", item)
        # Clamp selection index to new bounds and update state[name].
        idx = self._state.get(spec.name, -1)
        if not isinstance(idx, int):
            idx = -1
        if items and 0 <= idx < len(items):
            w.selection_clear(0, "end")
            w.selection_set(idx)
            w.see(idx)
        else:
            w.selection_clear(0, "end")
            self._state[spec.name] = -1
        self._emit_a11y_selection_change(spec)

    def _sync_listbox_items_for_specs(self,
                                      touched_keys: set[str] | None = None) -> None:
        for spec in self._widgets:
            if spec.kind != "listbox":
                continue
            items_key = spec.extras.get("items_key", f"{spec.name}_items")
            if touched_keys is None or items_key in touched_keys:
                self._sync_listbox_items(spec)

    def _combobox_values(self, spec: WidgetSpec) -> list[str]:
        values_key = spec.extras.get("values_key")
        if values_key is not None:
            values = self._state.get(values_key, [])
        else:
            values = spec.extras.get("values", [])
        return [str(v) for v in values] if isinstance(values, list) else []

    def _combobox_update_touches_values(self, update: dict[str, Any]) -> bool:
        for spec in self._widgets:
            if spec.kind != "combobox":
                continue
            values_key = spec.extras.get("values_key", f"{spec.name}_values")
            if values_key in update:
                return True
        return False

    def _sync_combobox_values(self, spec: WidgetSpec) -> None:
        w = self._tk_widgets.get(spec.name)
        if w is None or not isinstance(w, ttk.Combobox):
            return
        values = self._combobox_values(spec)
        w.configure(values=values)
        # If the current selection is no longer in values, clear it and
        # reset the associated state key so the user sees an empty pick.
        key = str(spec.extras.get("state_key", spec.name))
        current = self._state.get(key, "")
        if current not in values:
            w.set("")
            self._state[key] = ""
            var = self._tk_vars.get(key)
            if var is not None and isinstance(var, tk.StringVar):
                var.set("")

    def _sync_combobox_values_for_specs(self,
                                        touched_keys: set[str] | None = None) -> None:
        for spec in self._widgets:
            if spec.kind != "combobox":
                continue
            values_key = spec.extras.get("values_key", f"{spec.name}_values")
            if touched_keys is None or values_key in touched_keys:
                self._sync_combobox_values(spec)

    def _sync_treeview_selection(self, spec: WidgetSpec) -> None:
        tree = self._treeview_inner.get(spec.name)
        if tree is None:
            return
        idx = self._state.get(spec.name, -1)
        if not isinstance(idx, int) or idx < 0:
            return
        children = tree.get_children()
        if idx >= len(children):
            return
        iid = children[idx]
        if tree.selection() == (iid,):
            return
        tree.selection_set(iid)
        tree.focus(iid)
        tree.see(iid)
        self._emit_a11y_selection_change(spec)

    def _sync_treeview_selections(self) -> None:
        for spec in self._widgets:
            if spec.kind == "treeview":
                self._sync_treeview_selection(spec)

    def _populate_treeview(self, spec: WidgetSpec, *, force: bool = False) -> None:
        tree = self._treeview_inner.get(spec.name)
        if tree is None:
            return
        rows = self._treeview_rows(spec)
        sig = self._treeview_rows_signature(rows)
        if not force and self._treeview_row_cache.get(spec.name) == sig:
            self._sync_treeview_selection(spec)
            return
        self._treeview_row_cache[spec.name] = sig
        tree.delete(*tree.get_children())
        for row in rows:
            if isinstance(row, dict):
                col_ids = spec.extras.get("column_ids", [])
                values = tuple(row.get(cid, "") for cid in col_ids)
            elif isinstance(row, (list, tuple)):
                values = tuple(row)
            else:
                values = (str(row),)
            tree.insert("", tk.END, values=values)
        self._sync_treeview_selection(spec)

    def _sync_treeviews(self, *, force: bool = False) -> None:
        for spec in self._widgets:
            if spec.kind == "treeview":
                self._populate_treeview(spec, force=force)

    def _sync_progressbars(self) -> None:
        for spec in self._widgets:
            if spec.kind != "progressbar":
                continue
            w = self._tk_widgets.get(spec.name)
            if w is None or not isinstance(w, ttk.Progressbar):
                continue
            e = spec.extras
            key = e.get("state_key", spec.name)
            maximum = float(e.get("maximum", 100))
            base_mode: ProgressModeLike = e.get("mode", "determinate")
            running_key = f"{spec.name}_running"
            running = bool(self._state.get(running_key, False))

            if running or self._state.get(f"{spec.name}_mode") == "indeterminate":
                try:
                    w.stop()
                except tk.TclError:
                    pass
                w.configure(mode="indeterminate", maximum=maximum)  # type: ignore[arg-type]
                w.start(10)
                continue

            try:
                w.stop()
            except tk.TclError:
                pass
            w.configure(mode=base_mode, maximum=maximum)  # type: ignore[arg-type]
            raw = self._state.get(key, 0)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                value = 0.0
            value = max(0.0, min(maximum, value))
            w.configure(value=value)
            self._emit_a11y_value_change(spec)

    def _treeview_selected_index(self, spec: WidgetSpec) -> int:
        tree = self._treeview_inner.get(spec.name)
        if tree is None:
            return -1
        sel = tree.selection()
        if not sel:
            return -1
        return int(tree.index(sel[0]))

    # ── build & run ──

    def _widget_master(self, spec: WidgetSpec) -> tk.Misc:
        if self._root is None:
            raise RuntimeError("Tk root is not initialized")
        pane = spec.extras.get("pane")
        if pane and pane in self._pane_frames:
            return self._pane_frames[pane]
        return self._widget_masters.get(spec.name, self._root)

    def _tk_paned_orient(self, orient: OrientLike) -> OrientLike:
        return "horizontal" if orient == "horizontal" else "vertical"

    def _build_paned_widget(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        layout_opts = self._layout_paned_opts.get(spec.name, {})
        orient_str: OrientLike = layout_opts.get("orient", e.get("orient", "horizontal"))
        panes: tuple[str, ...] = e.get("panes", ())
        weights: list[int] = list(
            layout_opts.get("weights") or e.get("weights") or [1] * len(panes)
        )
        minsizes: list[int] = list(
            layout_opts.get("minsizes") or e.get("minsizes") or []
        )
        use_tk = any(
            (minsizes[i] if i < len(minsizes) else 0) > 0 for i in range(len(panes))
        )

        if use_tk:
            pw = tk.PanedWindow(
                master,
                orient=self._tk_paned_orient(orient_str),
                sashrelief=tk.RAISED,
                opaqueresize=True,
            )
            self._tk_widgets[spec.name] = pw
            self._paned_inner[spec.name] = pw  # type: ignore[assignment]
            for i, pane_id in enumerate(panes):
                frame = tk.Frame(pw)
                ms = int(minsizes[i]) if i < len(minsizes) else 0
                pw.add(frame, minsize=ms)
                self._pane_frames[pane_id] = frame
            return

        pw = ttk.Panedwindow(master, orient=orient_str)  # type: ignore[arg-type]
        sw = e.get("sashwidth")
        if sw is not None:
            try:
                pw.configure({"sashwidth": sw})
            except tk.TclError:
                pass  # ttk.Panedwindow: not available on all Tk builds
        self._tk_widgets[spec.name] = pw
        self._paned_inner[spec.name] = pw
        for i, pane_id in enumerate(panes):
            frame = ttk.Frame(pw)
            weight = weights[i] if i < len(weights) else 1
            pw.add(frame, weight=weight)
            self._pane_frames[pane_id] = frame

    def _pack_pane_child(self, spec: WidgetSpec) -> None:
        if not spec.extras.get("pane"):
            return
        w = self._tk_widgets.get(spec.name)
        if w is None:
            return
        if spec.kind in ("message", "text", "listbox", "treeview", "canvas"):
            w.pack(fill="both", expand=True, padx=t.SPACE[1], pady=t.SPACE[1])
        else:
            w.pack(fill="x", padx=t.SPACE[1], pady=t.SPACE[1])

    # ── widget builders: kind → builder registry ──
    #
    # Adding a widget kind means adding one builder (plus schema output).
    # Every built widget passes through the single a11y choke point
    # ``_apply_a11y`` so accessible name/role and focus behavior stay consistent.

    def _register_default_builders(self) -> None:
        self._widget_builders: dict[
            str, Callable[[WidgetSpec, tk.Misc], None]
        ] = {
            "label": self._build_label,
            "message": self._build_message,
            "button": self._build_button,
            "entry": self._build_entry,
            "checkbutton": self._build_checkbutton,
            "radiobutton": self._build_radiobutton,
            "text": self._build_text,
            "scale": self._build_scale,
            "spinbox": self._build_spinbox,
            "combobox": self._build_combobox,
            "listbox": self._build_listbox,
            "treeview": self._build_treeview,
            "canvas": self._build_canvas,
            "progressbar": self._build_progressbar,
            "bind": self._build_bind,
            "menubar": self._build_menubar,
        }

    def register_widget_builder(
        self,
        kind: str,
        builder: Callable[[TkApp, WidgetSpec, tk.Misc], None],
    ) -> None:
        """Register a builder for a custom widget kind.

        ``builder(app, spec, master)`` must create the widget and store it in
        ``app._tk_widgets`` — use the public runtime helpers where possible.
        The framework routes the spec through ``_apply_a11y`` afterwards, so
        custom kinds get the same accessibility wiring as core kinds.
        """
        def bound(spec: WidgetSpec, master: tk.Misc) -> None:
            builder(self, spec, master)
        self._widget_builders[kind] = bound

    def _build_widgets(self) -> None:
        """Create tkinter widgets from registered specs."""
        if self._root is None:
            return

        self._first_focusable: tk.Widget | None = None

        for spec in self._widgets:
            if spec.kind == "paned":
                master = self._widget_masters.get(spec.name, self._root)
                self._build_paned_widget(spec, master)
                self._apply_a11y(spec)

        for spec in self._widgets:
            if spec.kind == "paned":
                continue
            if spec.name in self._tk_widgets:
                # Pre-provided by a Layout chrome helper (e.g. ``.status()``
                # registers its styled status-bar label at mount time);
                # building again would stack a duplicate widget on top.
                self._apply_a11y(spec)
                continue
            builder = self._widget_builders.get(spec.kind)
            if builder is None:
                raise ValueError(
                    f"no builder registered for widget kind {spec.kind!r}"
                )
            builder(spec, self._widget_master(spec))
            if spec.extras.get("pane"):
                self._pack_pane_child(spec)
            self._apply_a11y(spec)
            if self._first_focusable is None:
                w = self._takefocus_widget(spec)
                if w is not None and self._is_focusable(w):
                    self._first_focusable = w

        self._apply_all_takefocus()

        # ── post-build: wire paired text y-scroll synchronization ──
        self._wire_text_scroll_sync()

        # ── post-build: annotate button labels with bind shortcuts ──
        self._annotate_button_shortcuts()

    def _is_focusable(self, w: tk.Widget) -> bool:
        """Return True if a widget can receive keyboard focus by default."""
        try:
            tf = w.cget("takefocus")
        except tk.TclError:
            return False
        if tf is True or tf == 1 or tf == "1":
            return True
        if tf == "" or tf is None or tf is False or tf == 0 or tf == "0":
            return False
        # ttk widgets may return a script (e.g. "ttk::takefocus"); treat any
        # non-falsy non-explicitly-disabled value as focusable.
        return bool(tf)

    def _set_initial_focus(self) -> None:
        """Move keyboard focus to the first focusable widget if none has it.

        Gives keyboard users a starting point in the Tab order
        (WCAG 2.1.1 Keyboard, 2.4.3 Focus Order). Respects ``on_ready`` or
        explicit user focus: if a widget already has focus, we leave it alone.

        On macOS the window manager may steal focus before the window is
        mapped, so we defer the actual focus_set until the next idle tick.
        """
        root = self._root
        if root is None:
            return

        def _apply() -> None:
            current = root.focus_get()
            if current is not None and current != root:
                return
            w = self._first_focusable
            if w is None:
                return
            try:
                w.focus_set()
                w.focus_force()
            except tk.TclError:
                pass

        try:
            root.after_idle(_apply)
        except tk.TclError:
            pass

    # ── a11y choke point ──

    def _a11y_target(self, spec: WidgetSpec) -> tk.Widget | None:
        if spec.kind in ("bind", "paned"):
            return None
        if spec.kind == "treeview":
            return self._treeview_inner.get(spec.name)
        if spec.kind == "text":
            return self._text_inner.get(spec.name)
        return self._tk_widgets.get(spec.name)

    def _wire_text_scroll_sync(self) -> None:
        """Connect y-scroll commands for paired text widgets after all are built."""
        for name_a, name_b in self._text_scroll_sync.items():
            text_a = self._text_inner.get(name_a)
            text_b = self._text_inner.get(name_b)
            if text_a is None or text_b is None:
                continue

            def _sync_from_a(*_args: Any, source: tk.Text = text_a, target: tk.Text = text_b) -> None:
                target.yview_moveto(source.yview()[0])

            def _sync_from_b(*_args: Any, source: tk.Text = text_b, target: tk.Text = text_a) -> None:
                target.yview_moveto(source.yview()[0])

            text_a.configure(yscrollcommand=_sync_from_a)
            text_b.configure(yscrollcommand=_sync_from_b)

    # ── a11y helpers (Tk 9.1+ / TIP 733) ──

    def _call_accessible(self, *args: str) -> bool:
        """Call ``tk accessible ...``, returning True on success.

        On the first ``TclError`` (Tk < 9.1) sets ``_acc_supported = False``
        so all subsequent calls short-circuit without touching the Tcl
        interpreter.
        """
        if self._root is None or self._acc_supported is False:
            return False
        try:
            self._root.tk.call("tk", "accessible", *args)
            self._acc_supported = True
            return True
        except tk.TclError:
            if self._acc_supported is None:
                self._acc_supported = False
            return False

    def _apply_a11y(self, spec: WidgetSpec) -> None:
        """Route ``WidgetSpec.role`` / ``description`` to Tk accessible attrs.

        Single choke point: every widget passes here after construction.
        On Tk 9.1+ (TIP 733) this calls ``tk accessible set_acc_*``; on older
        Tk the first failing call disables further attempts. Core widgets get
        reasonable defaults from Tk itself, so only user-provided traits are
        pushed. Role vocabulary mapping to Tk roles is tracked in ROADMAP
        (A11y implementation).
        """
        w = self._a11y_target(spec)
        if w is None:
            return
        if spec.role:
            self._call_accessible("set_acc_role", str(w), spec.role)
        if spec.description:
            self._call_accessible("set_acc_description", str(w), spec.description)

    def _apply_a11y_to_layout_frames(self) -> None:
        """Mark intermediate layout frames as grouping containers.

        ``Layout.section()`` creates ``tk.Frame`` wrappers that sit between
        the root and user widgets.  Without an explicit accessible role these
        frames can break MSAA focus tracking, causing NVDA to stay silent
        during Tab navigation.  Marking them as ``"Grouping"`` tells the
        accessibility tree to treat them as transparent layout helpers.
        """
        seen: set[int] = set()
        for frame in self._widget_masters.values():
            fid = id(frame)
            if fid in seen:
                continue
            seen.add(fid)
            if not self._call_accessible("set_acc_role", str(frame), "Grouping"):
                return

    def _emit_a11y_selection_change(self, spec: WidgetSpec) -> None:
        """Notify AT that the selection of *spec* has changed.

        Called automatically after ``_sync_treeview_selection`` and
        ``_sync_listbox_items``.  This is the key proof-point for
        "declarative → notifications are free": plain tkinter requires
        a manual ``tk accessible emit_selection_change`` call, but
        nextpytk's ``apply_state()`` already knows which widget was
        updated and can emit the event automatically.
        """
        w = self._a11y_target(spec)
        if w is None:
            return
        self._call_accessible("emit_selection_change", str(w))

    def _emit_a11y_value_change(self, spec: WidgetSpec) -> None:
        """Notify AT that the value of *spec* has changed.

        Called automatically after ``_sync_progressbars`` and other
        value-bearing widgets (scale, spinbox).  The current value is
        pushed via ``set_acc_value`` so screen readers can announce
        progress updates without polling.
        """
        w = self._a11y_target(spec)
        if w is None:
            return
        key = spec.extras.get("state_key", spec.name)
        value = str(self._state.get(key, ""))
        self._call_accessible("set_acc_value", str(w), value)

    def _emit_a11y_state_change(self, spec: WidgetSpec) -> None:
        """Notify AT that the checked/selected state of *spec* has changed.

        Called automatically after ``_sync_widget_states`` for
        checkbutton and radiobutton widgets.  Pushes the current
        ``state`` key value so screen readers can announce toggles.
        """
        w = self._a11y_target(spec)
        if w is None:
            return
        value = str(self._state.get(spec.name, ""))
        self._call_accessible("set_acc_value", str(w), value)

    # ── per-kind builders ──

    def _derive_ttk_style(
        self,
        base_style: str,
        style_name: str,
        overrides: dict[str, Any],
    ) -> str:
        """Create a unique derived ttk style that inherits the base layout.

        Some ttk widgets (Button, Entry, Checkbutton, Radiobutton) do not
        expose ``-font`` or ``-padding`` through widget ``configure()``.
        Copying the base style's layout and applying the overrides to a new
        style name lets users set these options declaratively while keeping
        all other theme properties (colors, maps, layout) from the base.
        """
        style = ttk.Style(self._root)
        style.layout(style_name, style.layout(base_style))
        style.configure(style_name, **overrides)
        return style_name

    def _build_label(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        style = "Heading.TLabel" if spec.role == "heading" else "TLabel"
        # Kizashi default is left-aligned; centering must be explicit.
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
            # Freeze the label width at the initial rendered text length so
            # later text changes cannot expand the window. Count full-width
            # characters as 2 columns to keep CJK text readable.
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

        # Focus ring is rendered as a 3px border whose color changes on focus
        # (WCAG 2.4.7 Focus Visible). The physical border always exists, so
        # the widget geometry never shifts.

        if spec.on_click is not None:
            fn = spec.on_click
            w.configure(command=lambda s=spec, f=fn: self._on_button_click(s, f))

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
        self._tk_vars[spec.name] = var
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
            w.bind("<FocusIn>", lambda _e, n=spec.name: self._entry_focus_in(n))
            w.bind("<FocusOut>", lambda _e, n=spec.name: self._entry_focus_out(n))
        if spec.on_update is not None:
            fn = spec.on_update
            w.bind("<KeyRelease>", lambda _e, s=spec, f=fn: self._on_entry_change(s, f))
        for sequence, handler in e.get("events", {}).items():
            w.bind(sequence, lambda _e, h=handler: self._on_entry_event(h))

    def _build_checkbutton(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        var = tk.StringVar(value="0")
        # padding is owned by the theme style (44px min target size);
        # a widget-level option here would silently override it.
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
        # anchor is a ttk layout option (style.layout), not a constructor kwarg
        # for ttk.Checkbutton; left alignment is enforced by the Kizashi style.
        self._tk_widgets[spec.name] = w
        self._tk_vars[key] = var
        if spec.on_update is not None:
            fn = spec.on_update
            w.configure(command=lambda s=spec, f=fn, v=var, k=key:
                        self._on_checkbutton_change(s, f, v, k))

    def _build_radiobutton(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        gk = e.get("group_key", "radio")
        val = e.get("rb_value", "")
        if gk not in self._tk_vars:
            self._tk_vars[gk] = tk.StringVar(value="")
        var = self._tk_vars[gk]
        # padding is owned by the theme style (44px min target size)
        style = "TRadiobutton"
        overrides: dict[str, Any] = {}
        if "font" in e:
            overrides["font"] = e["font"]
        if overrides:
            style = self._derive_ttk_style(
                style, f"Unique.{style}.{spec.name}", overrides
            )
        w = ttk.Radiobutton(
            master,
            text=spec.label_text,
            variable=var,
            value=val,
            style=style,
        )
        self._tk_widgets[spec.name] = w
        if spec.on_update is not None:
            fn = spec.on_update
            w.configure(command=lambda s=spec, f=fn, v=var, k=gk:
                        self._on_radiobutton_change(s, f, v, k))

    def _build_text(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        container = ttk.Frame(master)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
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
            wrap="word",
        )
        if e.get("font") is not None:
            w.configure(font=e["font"])
        scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=w.yview)
        w.configure(yscrollcommand=scroll.set)
        w.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self._tk_widgets[spec.name] = container
        self._text_inner[spec.name] = w

        tags: dict[str, dict[str, Any]] | None = e.get("tags")
        if tags:
            for tag_name, tag_kw in tags.items():
                w.tag_config(tag_name, **tag_kw)

        if e.get("readonly"):
            # Read-only: block user edits while keeping the widget focusable,
            # scrollable, and visible to assistive technologies. Tk's
            # state="disabled" hides the caret and removes the widget from
            # focus traversal, so we keep state="normal" and swallow only
            # editing events. This preserves accessible name/role/value
            # (WCAG 4.1.2) and keyboard focus with a visible indicator
            # (WCAG 2.4.7).
            w.bind("<Key>", lambda _e: "break")
            w.bind("<Button-1>", lambda _e: "break")
            w.bind("<B1-Motion>", lambda _e: "break")

        sync_with: str | None = e.get("sync_yscroll_with")
        if sync_with is not None:
            self._text_scroll_sync[spec.name] = sync_with

        if not e.get("tab_inserts", False):
            # By default, Tab moves focus out of the editor so users can
            # keyboard-traverse the form (WCAG 2.1.1, 2.4.3). Use Ctrl+Tab
            # (or Ctrl+I) to insert a literal tab. ``return "break"`` swallows
            # the event so the default tab-insertion behavior does not run.
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
                   self._on_text_change(s, f))

    def _build_scale(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        var = tk.IntVar(value=int(e.get("from", 0)))
        orient_str: OrientLike = e.get("orient", "horizontal")
        # The slider widget itself is narrow, so add external padding to give
        # it a larger click/touch target and keep adjacent controls at a
        # comfortable distance (WCAG 2.5.5 Target Size advisory).
        w = ttk.Scale(
            master,
            from_=e.get("from", 0),
            to=e.get("to", 100),
            orient=orient_str,
            variable=var,
            length=e.get("length", 200 if orient_str == "horizontal" else 100),
        )  # type: ignore[arg-type]
        self._tk_widgets[spec.name] = w
        self._tk_vars[key] = var
        self._state[key] = str(var.get())
        if spec.on_update is not None:
            fn = spec.on_update
            var.trace_add("write", lambda *_a, s=spec, f=fn, v=var, k=key:
                          self._on_var_change(s, f, v, k))

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
        self._tk_vars[key] = var
        if init_val:
            self._state[key] = init_val
        if spec.on_update is not None:
            fn = spec.on_update
            var.trace_add("write", lambda *_a, s=spec, f=fn, v=var, k=key:
                          self._on_var_change(s, f, v, k))

    def _build_combobox(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        values = self._combobox_values(spec)
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
        self._tk_vars[key] = var
        if init_val:
            self._state[key] = init_val
        if spec.on_update is not None:
            fn = spec.on_update
            var.trace_add("write", lambda *_a, s=spec, f=fn, v=var, k=key:
                          self._on_var_change(s, f, v, k))

    def _build_listbox(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        kwargs_lb: dict[str, Any] = {
            "bg": t.SURFACE,
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
        for item in self._listbox_items(spec):
            w.insert("end", item)
        self._tk_widgets[spec.name] = w
        # Initialize selection state to -1 so state[name] is always an integer
        # (matching treeview semantics) even before the user interacts.
        if spec.name not in self._state:
            self._state[spec.name] = -1
        if spec.on_update is not None:
            fn = spec.on_update
            w.bind("<<ListboxSelect>>", lambda _e, s=spec, f=fn:
                   self._on_listbox_select(s, f))
        for sequence, handler in e.get("events", {}).items():
            w.bind(sequence, lambda _e, h=handler: self._on_listbox_event(h))

    def _on_listbox_event(self, handler: ListboxEventHandler) -> None:
        """Invoke a widget-level listbox event handler and apply its state update."""
        result = self._dispatch("listbox_event", handler, dict(self._state))
        if isinstance(result, dict) and result:
            self._apply_state(result)

    def _build_treeview(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        col_ids: list[str] = e["column_ids"]
        col_configs: list[dict[str, Any]] = e["column_configs"]
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
                lambda ev, s=spec, f=fn: self._on_treeview_click(s, f, ev),
            )
        if spec.on_click is not None:
            fn_activate = spec.on_click
            tree.bind(
                "<Double-1>",
                lambda _e, s=spec, f=fn_activate: self._on_treeview_activate(s, f),
            )
        self._populate_treeview(spec)

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

    def _build_progressbar(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        maximum = float(e.get("maximum", 100))
        orient_str: OrientLike = e.get("orient", "horizontal")
        length = int(e.get("length", 200))
        pb_mode: ProgressModeLike = e.get("mode", "determinate")
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

    def _build_bind(self, spec: WidgetSpec, master: tk.Misc) -> None:
        self._register_bind(spec)

    def _register_bind(self, spec: WidgetSpec) -> None:
        """Apply a global key binding registered via @app.bind."""
        if self._root is None or spec.on_click is None:
            return
        for sequence, _label in spec.bindings:
            fn = spec.on_click
            self._root.bind_all(sequence, lambda _e, f=fn, s=spec: self._on_bind_trigger(s, f), add="+")

    def _on_bind_trigger(self, spec: WidgetSpec, fn: Any) -> None:
        """Handle a key binding trigger: invoke callback and apply state."""
        result = self._dispatch(spec.name, fn, dict(self._state))
        if isinstance(result, dict) and result:
            self._apply_state(result)

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

    # ── event handlers ──

    def _apply_callback_result(self, result: Any) -> None:
        if isinstance(result, dict):
            self._apply_state(result)

    def _on_button_click(self, spec: WidgetSpec, fn: Any) -> None:
        values = self._entry_values_dict()
        self._apply_callback_result(self._dispatch(spec.name, fn, values))

    def _on_entry_change(self, spec: WidgetSpec, fn: Any) -> None:
        value = self._entry_effective_value(spec.name)
        self._apply_callback_result(self._dispatch(spec.name, fn, value))

    def _on_entry_event(self, handler: ListboxEventHandler) -> None:
        """Invoke a widget-level entry event handler and apply its state update.

        Entry event handlers receive the current entry values dict (so they can
        read live text from all entries, including the one that fired) and return
        a state update dict, just like button callbacks.
        """
        values = self._entry_values_dict()
        result = self._dispatch("entry_event", handler, values)
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

    def _on_text_change(self, spec: WidgetSpec, fn: Any) -> None:
        w = self._text_inner.get(spec.name)
        value = ""
        if w is not None and hasattr(w, "get"):
            value = w.get("1.0", "end-1c")  # type: ignore[attr-defined]
        self._apply_callback_result(self._dispatch(spec.name, fn, value))

    def _on_listbox_select(self, spec: WidgetSpec, fn: ListboxSelectCallback) -> None:
        w = self._tk_widgets.get(spec.name)
        idx = -1
        if w is not None and hasattr(w, "curselection"):
            sel = w.curselection()  # type: ignore[attr-defined]
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

    def _on_treeview_activate(self, spec: WidgetSpec, fn: Any) -> None:
        idx = self._treeview_selected_index(spec)
        if idx < 0:
            return
        result = self._dispatch(spec.name, fn, idx)
        if isinstance(result, dict):
            self._state[spec.name] = idx
            self._apply_state_dict(result, full=False)

    def layout(self) -> LayoutBuilder:
        """Return a LayoutBuilder for declarative ``with``-block layout construction.

        Usage::

            with app.layout() as b:
                b.section("title")
                with b.grid():
                    b.col_weight(0, 0).col_weight(1, 1)
                    b.widget("celsius", sticky="ew")
                    b.widget("fahrenheit", sticky="ew")
            app.run(layout=b.build())
        """
        from nextpytk.layout import LayoutBuilder
        return LayoutBuilder()

    def run(
        self,
        *,
        layout: Any = None,
        initial_state: dict[str, Any] | None = None,
        multiview: str | None = None,
        stages: str | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        geometry: str | None = None,
    ) -> None:
        """Build and run the Tk application.

        on_ready is called after widget building and state application,
        just before "mainloop()". Use it for dynamic widget population,
        key bindings, or other imperative setup that needs widgets to exist.
        geometry: initial window size, e.g. "640x480".
        """
        used = sum(x is not None for x in (layout, multiview, stages))
        if used > 1:
            raise ValueError(
                "Only one of layout, multiview, or stages can be used in run()"
            )

        if stages is not None:
            cfg = self._stages.get(stages)
            if cfg is None:
                raise ValueError(f"Stages '{stages}' is not declared")
            declared_initial = cfg.get("initial_state") or {}
            merged_initial: dict[str, Any] | None
            if initial_state:
                merged_initial = {**declared_initial, **initial_state}
            else:
                merged_initial = declared_initial or None
            self.run_stages(
                stages=cfg["stages"],
                key=cfg["key"],
                toplevel_widgets=cfg["toplevel_widgets"],
                initial_state=merged_initial,
                view_layouts=cfg.get("view_layouts"),
                center_kinds=cfg.get("center_kinds"),
                on_ready=on_ready,
            )
            return

        if multiview is not None:
            cfg = self._multiviews.get(multiview)
            if cfg is None:
                raise ValueError(f"Multiview '{multiview}' is not declared")
            declared_initial = cfg.get("initial_state") or {}
            if initial_state:
                merged_initial = {**declared_initial, **initial_state}
            else:
                merged_initial = declared_initial or None
            self.run_multiview(
                views=cfg["views"],
                toplevel_widgets=cfg["toplevel_widgets"],
                initial_state=merged_initial,
                view_layouts=cfg.get("view_layouts"),
                center_kinds=cfg.get("center_kinds"),
                on_tab_change=cfg.get("on_tab_change"),
                on_ready=on_ready,
                tabposition=cfg.get("tabposition", "nw"),
            )
            return

        self._root = tk.Tk()
        self._root.title(self._title)
        if geometry:
            self._root.geometry(geometry)
        self._configure_theme(self._root)
        self.clear_runtime()

        if layout is not None:
            if isinstance(layout, list):
                from nextpytk.layout import Layout
                layout = Layout.from_list(layout)
            layout.mount_frames(self)

        self._build_widgets()

        if layout is not None:
            layout.pack_children(self)

        # Mark intermediate layout frames as grouping containers so they
        # don't block MSAA focus tracking (Tk 9.1+ / TIP 733).
        self._apply_a11y_to_layout_frames()

        if initial_state:
            self._apply_initial_state(initial_state)

        if on_ready is not None:
            on_ready(self)

        self._sync_widgets()
        self._sync_treeviews()
        self._sync_progressbars()
        self._sync_widget_states()
        self._set_initial_focus()
        self._root.mainloop()

    def run_async(
        self,
        *,
        layout: Any = None,
        initial_state: dict[str, Any] | None = None,
        multiview: str | None = None,
        stages: str | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        geometry: str | None = None,
    ) -> None:
        """Build and run the Tk application with asyncio event loop.

        Use ``app.spawn(coro)`` inside ``on_ready`` to schedule async tasks.
        geometry: initial window size, e.g. "640x480".
        """
        used = sum(x is not None for x in (layout, multiview, stages))
        if used > 1:
            raise ValueError(
                "Only one of layout, multiview, or stages can be used in run_async()"
            )

        if stages is not None:
            cfg = self._stages.get(stages)
            if cfg is None:
                raise ValueError(f"Stages '{stages}' is not declared")
            declared_initial = cfg.get("initial_state") or {}
            merged_initial: dict[str, Any] | None
            if initial_state:
                merged_initial = {**declared_initial, **initial_state}
            else:
                merged_initial = declared_initial or None
            asyncio.run(self._async_run_stages(
                stages=cfg["stages"],
                key=cfg["key"],
                toplevel_widgets=cfg["toplevel_widgets"],
                initial_state=merged_initial,
                view_layouts=cfg.get("view_layouts"),
                center_kinds=cfg.get("center_kinds"),
                on_ready=on_ready,
            ))
            return

        if multiview is not None:
            cfg = self._multiviews.get(multiview)
            if cfg is None:
                raise ValueError(f"Multiview '{multiview}' is not declared")
            declared_initial = cfg.get("initial_state") or {}
            if initial_state:
                merged_initial = {**declared_initial, **initial_state}
            else:
                merged_initial = declared_initial or None
            asyncio.run(self._async_run_multiview(
                views=cfg["views"],
                toplevel_widgets=cfg["toplevel_widgets"],
                initial_state=merged_initial,
                view_layouts=cfg.get("view_layouts"),
                center_kinds=cfg.get("center_kinds"),
                on_tab_change=cfg.get("on_tab_change"),
                on_ready=on_ready,
                tabposition=cfg.get("tabposition", "nw"),
            ))
            return

        asyncio.run(self._async_run(layout, initial_state, on_ready, geometry))

    async def _async_run_stages(
        self,
        *,
        stages: list[str],
        key: str,
        toplevel_widgets: tuple[str, ...] = (),
        initial_state: dict[str, Any] | None = None,
        view_layouts: dict[str, Layout] | None = None,
        center_kinds: set[str] | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
    ) -> None:
        """Async variant: stages setup + cooperative asyncio mainloop."""
        self._event_loop = asyncio.get_running_loop()
        self._setup_stages(
            name="__run_stages__",
            stages=stages,
            key=key,
            toplevel_widgets=toplevel_widgets,
            initial_state=initial_state,
            view_layouts=view_layouts,
            center_kinds=center_kinds,
            on_ready=on_ready,
        )
        await self._async_mainloop()

    async def _async_run(
        self,
        layout: Any | None,
        initial_state: dict[str, Any] | None,
        on_ready: Callable[[TkApp], None] | None,
        geometry: str | None = None,
    ) -> None:
        """Internal: build widgets and enter async mainloop."""
        self._root = tk.Tk()
        self._root.title(self._title)
        if geometry:
            self._root.geometry(geometry)
        self._configure_theme(self._root)
        self.clear_runtime()
        self._event_loop = asyncio.get_running_loop()

        if layout is not None:
            layout.mount_frames(self)

        self._build_widgets()

        if layout is not None:
            layout.pack_children(self)

        self._apply_a11y_to_layout_frames()

        if initial_state:
            self._apply_initial_state(initial_state)

        if on_ready is not None:
            on_ready(self)

        self._sync_widgets()
        self._sync_treeviews()
        self._sync_progressbars()
        self._sync_widget_states()
        self._set_initial_focus()
        await self._async_mainloop()

    # ── schema export (for AI agents / LLM Function Calling) ──

    def schema(self) -> dict[str, Any]:
        """Export widget registry as JSON-compatible schema."""
        widgets_out: list[dict[str, Any]] = []
        for w in self._widgets:
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
                values = self._combobox_values(w)
                d["values"] = values
                d["readonly"] = w.extras.get("readonly", False)
            if w.kind == "radiobutton":
                d["group_key"] = w.extras.get("group_key")
                d["rb_value"] = w.extras.get("rb_value")
            if w.kind == "listbox":
                d["items_key"] = w.extras.get("items_key")
                items = self._listbox_items(w)
                d["items_count"] = len(items)
            if w.kind == "treeview":
                d["columns"] = w.extras.get("column_ids", [])
                d["rows_key"] = w.extras.get("rows_key")
                d["rows_count"] = len(self._state.get(
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
                d["value"] = self._state.get(sk, 0)
            if w.kind == "entry":
                d["placeholder_as_hint"] = w.placeholder_as_hint
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
        return {"title": self._title, "widgets": widgets_out}

    @property
    def state(self) -> dict[str, Any]:
        return dict(self._state)
