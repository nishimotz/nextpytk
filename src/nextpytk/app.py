"""TkApp: Flask-inspired decorator API for tkinter.

Core idea:
- ``@app.label`` / ``@app.status`` / ``@app.button`` / ``@app.entry`` /
  ``@app.checkbutton`` / ``@app.radiobutton`` / ``@app.text`` /
  ``@app.scale`` / ``@app.spinbox`` / ``@app.listbox`` / ``@app.treeview`` /
  ``app.paned`` / ``app.progressbar`` register slots.
- Python owns nothing but schema + callbacks. Widget objects live in tkinter.
- Each decorated function returns a dict that merges into app's state.
- Layout is injected separately via Layout (DI / IoC).
- All widgets surface as JSON schema via ``app.schema()`` for agent consumption.
"""

from __future__ import annotations

import asyncio
import sys
import tkinter as tk
import tkinter.ttk as ttk
import traceback
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeVar

ProgressModeLike = Literal["determinate", "indeterminate"]

# Placeholder foreground: >= 4.5:1 contrast on both white and black
# backgrounds (DESIGN.md 付録 B A7 / WCAG 1.4.3).
PLACEHOLDER_FG = "#767676"

from nextpytk.types import (
    FillLike,
    OrientLike,
    SelectModeLike,
    SideLike,
    StateLike,
    TakeFocusLike,
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

# ── callback type aliases ──

# label/status: no arg, returns str or state dict
LabelCallback = Callable[[], str | dict[str, Any]]

# button: receives entry values dict, returns state dict
ButtonCallback = Callable[[dict[str, Any]], dict[str, Any]]
BindCallback = ButtonCallback  # bind: same signature: state dict → state dict

# entry / text / listbox / scale / spinbox: receives value str, returns state dict
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
        "listbox", "treeview", "paned", "progressbar", "canvas",
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
    """Flask-inspired Tk application with decorator API and DI layout.

    Inversion of Control (IoC): decorators register intent,
    Layout provides structure. Decoupled — classic IoC.
    """

    def __init__(self, title: str = "Flask-style decorator", *, debug: bool = False):
        self._title = title
        self._debug = debug
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
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._jobs: dict[str, AsyncJob] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._treeview_inner: dict[str, ttk.Treeview] = {}
        self._treeview_row_cache: dict[str, tuple[Any, ...]] = {}
        self._paned_inner: dict[str, ttk.Panedwindow] = {}
        self._pane_frames: dict[str, tk.Widget] = {}
        self._layout_paned_opts: dict[str, dict[str, Any]] = {}
        self._current_pane: str | None = None
        self._register_default_builders()

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
        """Run a user callback under the framework error policy (原則 6).

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

    def set_root(self, root: tk.Tk) -> None:
        self._root = root

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
    ) -> Callable[[F], F]:
        """Declare a multiview configuration by name.

        Example::

            @app.multiview("main", views=["Home", "Settings"])
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
        }
        self._multiviews[name] = cfg

        def decorator(fn: F) -> F:
            return fn

        return decorator

    def build_widgets(self) -> None:
        self._build_widgets()

    def widget(self, name: str) -> tk.Widget | None:
        return self._tk_widgets.get(name)

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

    def apply_state(self, update: dict[str, Any]) -> None:
        self._apply_state(update)

    def sync(self) -> None:
        self._sync_widgets()
        self._sync_widget_states()

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
    ) -> None:
        """Build and run the app in a ttk.Notebook container.

        This keeps examples close to ``app.run(layout=...)`` style while supporting
        multi-view/tab UIs.
        """
        root = self._setup_multiview(
            views=views,
            toplevel_widgets=toplevel_widgets,
            initial_state=initial_state,
            view_layouts=view_layouts,
            center_kinds=center_kinds,
            on_tab_change=on_tab_change,
            on_ready=on_ready,
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
    ) -> tk.Tk:
        """Build the Notebook UI; everything except entering a mainloop."""
        root = tk.Tk()
        root.title(self._title)
        self.set_root(root)
        self.clear_runtime()

        nb = ttk.Notebook(root)
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

        for name in toplevel_widgets:
            self.set_widget_master(name, root)

        for view in views:
            frame = tk.Frame(nb, name=f"tabframe_{view}")
            frames[view] = frame
            if view in layouts:
                layout = layouts[view]
                allowed = set(self.view_widget_names(view))
                row_jobs, grid_jobs = layout.mount_frames_into(
                    self, frame, allowed_widgets=allowed)
                jobs_by_view[view] = (layout, row_jobs, grid_jobs)
            else:
                for wname in self.view_widget_names(view):
                    self.set_widget_master(wname, frame)

        self.build_widgets()

        if initial_state:
            self.apply_state(initial_state)

        for name in toplevel_widgets:
            w = self.widget(name)
            if w is not None:
                w.pack(fill="x", padx=5, pady=1)

        nb.pack(fill="both", expand=True, padx=5, pady=5)
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
        pady: int = 2,
    ) -> None:
        """Pack all widgets registered in a named view."""
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
        *,
        role: str | None = None,
        description: str | None = None,
        font: tuple[str, int] | tuple[str, int, str] | None = None,
        anchor: str | None = None,
        justify: str | None = None,
        padding: int | tuple[int, int] | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a label. Decorated function returns text or state dict.

        ``takefocus``: Tab key traversal (``0`` / ``1`` / ``\"\"`` or bool).
        """
        def decorator(fn: LabelCallback) -> LabelCallback:
            extras: dict[str, Any] = {}
            if font is not None:
                extras["font"] = font
            if anchor is not None:
                extras["anchor"] = anchor
            if justify is not None:
                extras["justify"] = justify
            if padding is not None:
                extras["padding"] = padding
            self._add_spec(WidgetSpec(
                name=name, kind="label", role=role, description=description,
                on_update=fn,
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def status(
        self,
        name: str,
        *,
        role: str | None = "status",
        description: str | None = None,
        font: tuple[str, int] | tuple[str, int, str] | None = None,
        anchor: str | None = None,
        justify: str | None = None,
        padding: int | tuple[int, int] | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a label with ``role=\"status\"``."""
        return self.label(
            name,
            role=role,
            description=description,
            font=font,
            anchor=anchor,
            justify=justify,
            padding=padding,
            takefocus=takefocus,
        )

    def bind(
        self,
        name: str,
        *,
        sequence: str,
        label: str = "",
        description: str | None = None,
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
        *,
        role: str | None = None,
        description: str | None = None,
        width: int | None = None,
        auto_width: bool = True,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a message widget with wrap support.

        ``width``: initial wrap width in pixels. If omitted and ``auto_width=True``,
        width follows parent container resize.
        """
        def decorator(fn: LabelCallback) -> LabelCallback:
            extras: dict[str, Any] = {"auto_width": auto_width}
            if width is not None:
                extras["width"] = width
            self._add_spec(WidgetSpec(
                name=name, kind="message", role=role, description=description,
                on_update=fn,
                extras=self._widget_extras(extras, takefocus=takefocus),
            ))
            return fn
        return decorator

    def button(
        self,
        name: str,
        *,
        label: str = "",
        role: str | None = "button",
        description: str | None = None,
        state: StateLike = "normal",
        enabled_if: Callable[[dict[str, Any]], bool] | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[ButtonCallback], ButtonCallback]:
        """Register a button. Callback receives entry values dict → returns state dict.

        ``state``: initial widget state (``"normal"`` / ``"disabled"``).
        When ``enabled_if`` is set, it takes over after the first sync.
        """
        def decorator(fn: ButtonCallback) -> ButtonCallback:
            extras: dict[str, Any] = {}
            if state != "normal":
                extras["state"] = state
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
        *,
        placeholder: str = "",
        placeholder_as_hint: bool = True,
        role: str | None = None,
        description: str | None = None,
        state: StateLike = "normal",
        show: str | None = None,
        width: int | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register an entry. Callback receives value string → returns state dict.

        ``show``: set ``\"*\"`` for password entry.
        ``width``: character width.
        ``state``: initial widget state (``"normal"`` / ``"disabled"``).
        """
        def decorator(fn: ValueCallback) -> ValueCallback:
            extras: dict[str, Any] = {}
            if show is not None:
                extras["show"] = show
            if width is not None:
                extras["width"] = width
            if state != "normal":
                extras["state"] = state
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
        *,
        text: str = "",
        key: str | None = None,
        description: str | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[BoolCallback], BoolCallback]:
        """Register a checkbutton. Callback receives bool → returns state dict.

        ``state[key]`` is ``\"1\"`` or ``\"0\"``. Key defaults to name.
        """
        actual_key = key or name
        def decorator(fn: BoolCallback) -> BoolCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="checkbutton", label_text=text,
                description=description, on_update=fn,
                extras=self._widget_extras(
                    {"state_key": actual_key}, takefocus=takefocus,
                ),
            ))
            return fn
        return decorator

    def radiobutton(
        self,
        name: str,
        *,
        text: str = "",
        value: str = "",
        group: str = "radio",
        description: str | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a radiobutton. Callback receives selected value → returns state dict.

        All radiobuttons sharing the same *group* write to ``state[group]``.
        """
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="radiobutton", label_text=text,
                description=description, on_update=fn,
                extras=self._widget_extras(
                    {"rb_value": value, "group_key": group},
                    takefocus=takefocus,
                ),
            ))
            return fn
        return decorator

    def text(
        self,
        name: str,
        *,
        width: int = 50,
        height: int = 8,
        description: str | None = None,
        state: StateLike = "normal",
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a multiline text widget. Callback receives full content → returns state dict."""
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="text", description=description,
                on_update=fn,
                extras=self._widget_extras(
                    {"width": width, "height": height},
                    takefocus=takefocus,
                ),
            ))
            return fn
        return decorator

    def scale(
        self,
        name: str,
        *,
        key: str | None = None,
        from_: int = 0,
        to: int = 100,
        orient: OrientLike = "horizontal",
        description: str | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a scale slider. Callback receives current value → returns state dict.

        ``state[key]`` holds the int value. Key defaults to name.
        """
        actual_key = key or name
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
        *,
        key: str | None = None,
        from_: float | None = None,
        to: float | None = None,
        values: list[str] | None = None,
        description: str | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a spinbox. Callback receives current value → returns state dict.

        ``state[key]`` holds the string value. Key defaults to name.
        """
        actual_key = key or name
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._add_spec(WidgetSpec(
                name=name, kind="spinbox", description=description,
                on_update=fn,
                extras=self._widget_extras({
                    "state_key": actual_key, "from": from_,
                    "to": to, "values": values,
                }, takefocus=takefocus),
            ))
            return fn
        return decorator

    def listbox(
        self,
        name: str,
        *,
        items: list[str] | None = None,
        selectmode: SelectModeLike = "browse",
        height: int | None = None,
        description: str | None = None,
        enabled_if: Callable[[dict[str, Any]], bool] | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a listbox. Callback receives selected item → returns state dict.

        ``state[name]`` holds the selected item string.
        ``enabled_if``: disables selection when False (sets selectmode="none").
        """
        def decorator(fn: ValueCallback) -> ValueCallback:
            extras: dict[str, Any] = {"items": items or [], "selectmode": selectmode}
            if height is not None:
                extras["height"] = height
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
        *,
        columns: list[Any],
        rows_key: str | None = None,
        selectmode: SelectModeLike = "browse",
        height: int = 8,
        description: str | None = None,
        activate: TreeviewActivateCallback | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[TreeviewSelectCallback], TreeviewSelectCallback]:
        """Register a flat ``ttk.Treeview`` table (``show=\"headings\"``).

        ``columns``: list of ``(id, heading)`` / ``(id, heading, width)``
        or ``(id, heading, width, anchor)`` tuples, or dicts with
        ``id``, ``heading``, ``width``, ``anchor``, ``stretch``.

        ``state[rows_key]``: list of row value tuples (column order).
        ``rows_key`` defaults to ``\"{name}_rows\"``.

        ``state[name]``: selected row index (``int``, ``-1`` if none).

        ``activate``: optional double-click handler (same signature as select).
        """
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
        *,
        panes: tuple[str, ...] | list[str],
        orient: OrientLike = "horizontal",
        weights: tuple[int, ...] | list[int] | None = None,
        sashwidth: int | None = 4,
        description: str | None = None,
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
        *,
        key: str | None = None,
        maximum: float = 100.0,
        mode: ProgressModeLike = "determinate",
        length: int = 200,
        orient: OrientLike = "horizontal",
        description: str | None = None,
    ) -> None:
        """Register a ``ttk.Progressbar`` driven by app state.

        ``state[key]``: numeric value ``0 .. maximum`` (determinate).
        ``state[\"{name}_running\"]``: when ``True``, runs indeterminate
        animation (``start()``); when ``False``, ``stop()`` and restore mode.

        ``key`` defaults to ``name``. Update via ``apply_state`` from buttons
        or ``app.spawn`` / ``@app.job`` async tasks.
        """
        actual_key = key or name
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
        *,
        width: int = 300,
        height: int = 200,
        bg: str = "#f0f0f0",
        description: str | None = None,
        items: list | None = None,
        takefocus: TakeFocusLike | None = None,
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Register a canvas (display only).

        ``items``: list of ``(kind, *args, kwargs)`` to draw via ``create_{kind}``.
        """
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
        self._state.update(update)
        for key, val in update.items():
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
            self._sync_widgets_for_keys(update)
        if self._treeview_update_touches_rows(update):
            self._sync_treeviews(force=True)
        elif full and self._treeview_update_touches_selection(update):
            self._sync_treeview_selections()
        if full:
            self._sync_progressbars()
            self._sync_widget_states()

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
        """Push state to label widgets."""
        for spec in self._widgets:
            if spec.kind not in ("label", "status", "message"):
                continue
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
        """Update only label/status/message widgets named in *update*."""
        for spec in self._widgets:
            if spec.kind not in ("label", "status", "message"):
                continue
            if spec.name not in update:
                continue
            tk_w = self._tk_widgets.get(spec.name)
            if tk_w is None:
                continue
            tk_w.configure(text=str(update[spec.name]))  # type: ignore[call-arg]

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
            w.pack(fill="both", expand=True, padx=4, pady=4)
        else:
            w.pack(fill="x", padx=4, pady=2)

    # ── widget builders: kind → builder registry ──
    #
    # Adding a widget kind means adding one builder (plus schema output).
    # Every built widget passes through the single a11y choke point
    # ``_apply_a11y`` (DESIGN.md 原則 2 / 付録 B).

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
            "listbox": self._build_listbox,
            "treeview": self._build_treeview,
            "canvas": self._build_canvas,
            "progressbar": self._build_progressbar,
            "bind": self._build_bind,
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

        for spec in self._widgets:
            if spec.kind == "paned":
                master = self._widget_masters.get(spec.name, self._root)
                self._build_paned_widget(spec, master)
                self._apply_a11y(spec)

        for spec in self._widgets:
            if spec.kind == "paned":
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

        self._apply_all_takefocus()

        # ── post-build: annotate button labels with bind shortcuts ──
        self._annotate_button_shortcuts()

    # ── a11y choke point ──

    def _a11y_target(self, spec: WidgetSpec) -> tk.Widget | None:
        if spec.kind in ("bind", "paned"):
            return None
        if spec.kind == "treeview":
            return self._treeview_inner.get(spec.name)
        return self._tk_widgets.get(spec.name)

    def _apply_a11y(self, spec: WidgetSpec) -> None:
        """Route ``WidgetSpec.role`` / ``description`` to Tk accessible attrs.

        Single choke point: every widget passes here after construction.
        On Tk 9.1+ (TIP 733) this calls ``tk accessible set_acc_*``; on older
        Tk the first failing call disables further attempts. Core widgets get
        reasonable defaults from Tk itself, so only user-provided traits are
        pushed. Role vocabulary mapping to Tk roles is tracked in ROADMAP
        (A11y 実適用).
        """
        w = self._a11y_target(spec)
        if w is None or self._root is None or self._acc_supported is False:
            return
        traits: list[tuple[str, str]] = []
        if spec.role:
            traits.append(("set_acc_role", spec.role))
        if spec.description:
            traits.append(("set_acc_description", spec.description))
        if not traits:
            return
        try:
            for cmd, value in traits:
                self._root.tk.call("tk", "accessible", cmd, str(w), value)
            self._acc_supported = True
        except tk.TclError:
            # Tk < 9.1 has no `tk accessible`; don't retry per widget.
            if self._acc_supported is None:
                self._acc_supported = False

    # ── per-kind builders ──

    def _build_label(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        w = ttk.Label(master, text="", anchor="center", justify="center")
        for opt in ("font", "anchor", "justify", "padding"):
            if opt in e:
                w.configure(**{opt: e[opt]})
        self._tk_widgets[spec.name] = w
        if spec.on_update is not None:
            result = self._dispatch(spec.name, spec.on_update)
            if isinstance(result, str):
                w.configure(text=result)
            elif isinstance(result, dict):
                w.configure(text=str(result.get(spec.name, "")))

    def _build_message(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        w = tk.Message(master, text="", name=spec.name)
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
        w = ttk.Button(master, text=spec.label_text or spec.name)
        if "state" in spec.extras:
            w.configure(state=spec.extras["state"])
        self._tk_widgets[spec.name] = w
        if spec.on_click is not None:
            fn = spec.on_click
            w.configure(command=lambda s=spec, f=fn: self._on_button_click(s, f))

    def _build_entry(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        var = tk.StringVar(value="")
        w = ttk.Entry(master, textvariable=var)
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

    def _build_checkbutton(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        var = tk.StringVar(value="0")
        w = ttk.Checkbutton(master, text=spec.label_text, variable=var,
                            onvalue="1", offvalue="0")
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
        w = ttk.Radiobutton(master, text=spec.label_text, variable=var,
                            value=val)
        self._tk_widgets[spec.name] = w
        if spec.on_update is not None:
            fn = spec.on_update
            w.configure(command=lambda s=spec, f=fn, v=var, k=gk:
                        self._on_radiobutton_change(s, f, v, k))

    def _build_text(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        w = tk.Text(master, width=e.get("width", 50), height=e.get("height", 8),
                    name=spec.name)
        self._tk_widgets[spec.name] = w
        if spec.on_update is not None:
            fn = spec.on_update
            w.bind("<KeyRelease>", lambda _e, s=spec, f=fn:
                   self._on_text_change(s, f))

    def _build_scale(self, spec: WidgetSpec, master: tk.Misc) -> None:
        e = spec.extras
        key = e.get("state_key", spec.name)
        var = tk.IntVar(value=int(e.get("from", 0)))
        orient_str: OrientLike = e.get("orient", "horizontal")
        w = ttk.Scale(master, from_=e.get("from", 0), to=e.get("to", 100),
                      orient=orient_str, variable=var)  # type: ignore[arg-type]
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
        w = ttk.Spinbox(master, textvariable=var, **kwargs)
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
        kwargs_lb: dict[str, Any] = {}
        if e.get("height"):
            kwargs_lb["height"] = e["height"]
        if e.get("selectmode"):
            kwargs_lb["selectmode"] = e["selectmode"]
        w = tk.Listbox(master, name=spec.name, **kwargs_lb)
        for item in e.get("items", []):
            w.insert("end", item)
        self._tk_widgets[spec.name] = w
        if spec.on_update is not None:
            fn = spec.on_update
            w.bind("<<ListboxSelect>>", lambda _e, s=spec, f=fn:
                   self._on_listbox_select(s, f))

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
        w = tk.Canvas(master, width=e.get("width", 300), height=e.get("height", 200),
                      bg=e.get("bg", "#f0f0f0"), name=spec.name)
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
        w = self._tk_widgets.get(spec.name)
        value = ""
        if w is not None and hasattr(w, "get"):
            value = w.get("1.0", "end-1c")  # type: ignore[attr-defined]
        self._apply_callback_result(self._dispatch(spec.name, fn, value))

    def _on_listbox_select(self, spec: WidgetSpec, fn: Any) -> None:
        w = self._tk_widgets.get(spec.name)
        value = ""
        if w is not None and hasattr(w, "curselection"):
            sel = w.curselection()  # type: ignore[attr-defined]
            if sel and hasattr(w, "get"):
                value = w.get(sel[0])  # type: ignore[attr-defined]
        self._state[spec.name] = value
        self._apply_callback_result(self._dispatch(spec.name, fn, value))

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
                with b.grid(col_weights=(0, 1)):
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
        on_ready: Callable[[TkApp], None] | None = None,
        geometry: str | None = None,
    ) -> None:
        """Build and run the Tk application.

        on_ready is called after widget building and state application,
        just before "mainloop()". Use it for dynamic widget population,
        key bindings, or other imperative setup that needs widgets to exist.
        geometry: initial window size, e.g. "640x480".
        """
        if multiview is not None:
            if layout is not None:
                raise ValueError("layout and multiview cannot be used together in run()")
            cfg = self._multiviews.get(multiview)
            if cfg is None:
                raise ValueError(f"Multiview '{multiview}' is not declared")
            declared_initial = cfg.get("initial_state") or {}
            merged_initial: dict[str, Any] | None
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
            )
            return

        self._root = tk.Tk()
        self._root.title(self._title)
        if geometry:
            self._root.geometry(geometry)
        self.clear_runtime()

        if layout is not None:
            if isinstance(layout, list):
                from nextpytk.layout import Layout
                layout = Layout.from_list(layout)
            layout.mount_frames(self)

        self._build_widgets()

        if layout is not None:
            layout.pack_children(self)

        if initial_state:
            self.apply_state(initial_state)

        if on_ready is not None:
            on_ready(self)

        self._sync_widgets()
        self._sync_treeviews()
        self._sync_progressbars()
        self._sync_widget_states()
        self._root.mainloop()

    def run_async(
        self,
        *,
        layout: Any = None,
        initial_state: dict[str, Any] | None = None,
        multiview: str | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        geometry: str | None = None,
    ) -> None:
        """Build and run the Tk application with asyncio event loop.

        Use ``app.spawn(coro)`` inside ``on_ready`` to schedule async tasks.
        geometry: initial window size, e.g. "640x480".
        """
        if multiview is not None:
            if layout is not None:
                raise ValueError(
                    "layout and multiview cannot be used together in run_async()"
                )
            cfg = self._multiviews.get(multiview)
            if cfg is None:
                raise ValueError(f"Multiview '{multiview}' is not declared")
            declared_initial = cfg.get("initial_state") or {}
            merged_initial: dict[str, Any] | None
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
            ))
            return

        asyncio.run(self._async_run(layout, initial_state, on_ready, geometry))

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
        self.clear_runtime()
        self._event_loop = asyncio.get_running_loop()

        if layout is not None:
            layout.mount_frames(self)

        self._build_widgets()

        if layout is not None:
            layout.pack_children(self)

        if initial_state:
            self.apply_state(initial_state)

        if on_ready is not None:
            on_ready(self)

        self._sync_widgets()
        self._sync_treeviews()
        self._sync_progressbars()
        self._sync_widget_states()
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
            if w.kind in ("checkbutton", "scale", "spinbox"):
                d["state_key"] = w.extras.get("state_key")
            if w.kind == "radiobutton":
                d["group_key"] = w.extras.get("group_key")
                d["rb_value"] = w.extras.get("rb_value")
            if w.kind == "listbox":
                d["items_count"] = len(w.extras.get("items", []))
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
            if "takefocus" in w.extras:
                d["takefocus"] = w.extras["takefocus"]
            widgets_out.append(d)
        return {"title": self._title, "widgets": widgets_out}

    @property
    def state(self) -> dict[str, Any]:
        return dict(self._state)
