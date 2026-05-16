"""TkApp: Flask-inspired decorator API for tkinter.

Core idea:
- ``@app.label`` / ``@app.status`` / ``@app.button`` / ``@app.entry`` /
  ``@app.checkbutton`` / ``@app.radiobutton`` / ``@app.text`` /
  ``@app.scale`` / ``@app.spinbox`` / ``@app.listbox`` register slots.
- Python owns nothing but schema + callbacks. Widget objects live in tkinter.
- Each decorated function returns a dict that merges into app's state.
- Layout is injected separately via Layout (DI / IoC).
- All widgets surface as JSON schema via ``app.schema()`` for agent consumption.
"""

from __future__ import annotations

import asyncio
import tkinter as tk
import tkinter.ttk as ttk
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar

from tkouter.types import FillLike, OrientLike, SelectModeLike, SideLike, StateLike
from tkouter.widgets import WidgetSpec

if TYPE_CHECKING:
    from tkouter.layout import Layout, LayoutBuilder

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

# entry / text / listbox / scale / spinbox: receives value str, returns state dict
ValueCallback = Callable[[str], dict[str, Any]]

# checkbutton: receives bool, returns state dict
BoolCallback = Callable[[bool], dict[str, Any]]

# radiobutton: receives selected value str, returns state dict


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

    def label(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.label(name, **kw)

    def status(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.status(name, **kw)

    def message(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.message(name, **kw)

    def button(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.button(name, **kw)

    def entry(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.entry(name, **kw)

    def checkbutton(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.checkbutton(name, **kw)

    def radiobutton(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.radiobutton(name, **kw)

    def text(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.text(name, **kw)

    def scale(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.scale(name, **kw)

    def spinbox(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.spinbox(name, **kw)

    def listbox(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.listbox(name, **kw)

    def canvas(self, name: str, **kw: Any):
        self._app._view_widgets[self._name].append(name)
        return self._app.canvas(name, **kw)


class TkApp:
    """Flask-inspired Tk application with decorator API and DI layout.

    Inversion of Control (IoC): decorators register intent,
    Layout provides structure. Decoupled — classic IoC.
    """

    def __init__(self, title: str = "Flask-style decorator"):
        self._title = title
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

    def apply_state(self, update: dict[str, Any] | str) -> None:
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
                    from tkouter.layout import Layout
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
        root.mainloop()

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
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a label. Decorated function returns text or state dict."""
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
            self._widgets.append(WidgetSpec(
                name=name, kind="label", role=role, description=description,
                on_update=fn, extras=extras,
            ))
            return fn
        return decorator

    def status(
        self,
        name: str,
        *,
        role: str | None = "status",
        description: str | None = None,
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a label with ``role=\"status\"``."""
        return self.label(name, role=role, description=description)

    def message(
        self,
        name: str,
        *,
        role: str | None = None,
        description: str | None = None,
        width: int | None = None,
        auto_width: bool = True,
    ) -> Callable[[LabelCallback], LabelCallback]:
        """Register a message widget with wrap support.

        ``width``: initial wrap width in pixels. If omitted and ``auto_width=True``,
        width follows parent container resize.
        """
        def decorator(fn: LabelCallback) -> LabelCallback:
            extras: dict[str, Any] = {"auto_width": auto_width}
            if width is not None:
                extras["width"] = width
            self._widgets.append(WidgetSpec(
                name=name, kind="message", role=role, description=description,
                on_update=fn, extras=extras,
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
    ) -> Callable[[ButtonCallback], ButtonCallback]:
        """Register a button. Callback receives entry values dict → returns state dict."""
        def decorator(fn: ButtonCallback) -> ButtonCallback:
            self._widgets.append(WidgetSpec(
                name=name, kind="button", label_text=label, role=role,
                description=description, on_click=fn, enabled_if=enabled_if,
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
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register an entry. Callback receives value string → returns state dict.

        ``show``: set ``\"*\"`` for password entry.
        ``width``: character width.
        """
        def decorator(fn: ValueCallback) -> ValueCallback:
            extras = {}
            if show is not None:
                extras["show"] = show
            if width is not None:
                extras["width"] = width
            self._widgets.append(WidgetSpec(
                name=name, kind="entry", placeholder=placeholder,
                placeholder_as_hint=placeholder_as_hint,
                role=role, description=description, on_update=fn,
                extras=extras,
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
    ) -> Callable[[BoolCallback], BoolCallback]:
        """Register a checkbutton. Callback receives bool → returns state dict.

        ``state[key]`` is ``\"1\"`` or ``\"0\"``. Key defaults to name.
        """
        actual_key = key or name
        def decorator(fn: BoolCallback) -> BoolCallback:
            self._widgets.append(WidgetSpec(
                name=name, kind="checkbutton", label_text=text,
                description=description, on_update=fn,
                extras={"state_key": actual_key},
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
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a radiobutton. Callback receives selected value → returns state dict.

        All radiobuttons sharing the same *group* write to ``state[group]``.
        """
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._widgets.append(WidgetSpec(
                name=name, kind="radiobutton", label_text=text,
                description=description, on_update=fn,
                extras={"rb_value": value, "group_key": group},
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
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a multiline text widget. Callback receives full content → returns state dict."""
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._widgets.append(WidgetSpec(
                name=name, kind="text", description=description,
                on_update=fn,
                extras={"width": width, "height": height},
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
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a scale slider. Callback receives current value → returns state dict.

        ``state[key]`` holds the int value. Key defaults to name.
        """
        actual_key = key or name
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._widgets.append(WidgetSpec(
                name=name, kind="scale", description=description,
                on_update=fn,
                extras={"state_key": actual_key, "from": from_,
                        "to": to, "orient": orient},
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
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a spinbox. Callback receives current value → returns state dict.

        ``state[key]`` holds the string value. Key defaults to name.
        """
        actual_key = key or name
        def decorator(fn: ValueCallback) -> ValueCallback:
            self._widgets.append(WidgetSpec(
                name=name, kind="spinbox", description=description,
                on_update=fn,
                extras={"state_key": actual_key, "from": from_,
                        "to": to, "values": values},
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
    ) -> Callable[[ValueCallback], ValueCallback]:
        """Register a listbox. Callback receives selected item → returns state dict.

        ``state[name]`` holds the selected item string.
        ``enabled_if``: disables selection when False (sets selectmode="none").
        """
        def decorator(fn: ValueCallback) -> ValueCallback:
            extras: dict[str, Any] = {"items": items or [], "selectmode": selectmode}
            if height is not None:
                extras["height"] = height
            self._widgets.append(WidgetSpec(
                name=name, kind="listbox", description=description,
                on_update=fn, extras=extras, enabled_if=enabled_if,
            ))
            return fn
        return decorator

    def canvas(
        self,
        name: str,
        *,
        width: int = 300,
        height: int = 200,
        bg: str = "#f0f0f0",
        description: str | None = None,
        items: list | None = None,
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Register a canvas (display only).

        ``items``: list of ``(kind, *args, kwargs)`` to draw via ``create_{kind}``.
        """
        def decorator(fn: Callable[[], None] | None = None) -> Callable[[], None]:
            extras: dict[str, Any] = {"width": width, "height": height, "bg": bg}
            if items:
                extras["items"] = items
            self._widgets.append(WidgetSpec(
                name=name, kind="canvas", description=description,
                extras=extras,
            ))
            return fn  # type: ignore[return-value]
        return decorator

    # ── state management ──

    def _apply_state(self, update: dict[str, Any] | str) -> None:
        if isinstance(update, str):
            self._state["_last"] = update
        elif isinstance(update, dict):
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
        self._sync_widgets()
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
                if ok:
                    orig_sm = str(spec.extras.get("selectmode", "browse"))
                    tk_w.configure(state="normal", selectmode=orig_sm)
                else:
                    tk_w.selection_clear(0, "end")
                    tk_w.configure(state="disabled")

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
            if getattr(w, "_tkouter_ph_active", False):
                return ""
            ph = getattr(w, "_tkouter_placeholder", "") or ""
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
            ph = getattr(w, "_tkouter_placeholder", "") or ""
            if not ph:
                return
            if getattr(w, "_tkouter_ph_active", False) or var.get() == ph:
                var.set("")
                setattr(w, "_tkouter_ph_active", False)
                try:
                    w.configure(foreground=getattr(w, "_tkouter_fg_normal",
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
            ph = getattr(w, "_tkouter_placeholder", "") or ""
            if not ph:
                return
            if not var.get().strip():
                var.set(ph)
                setattr(w, "_tkouter_ph_active", True)
                try:
                    w.configure(foreground="grey")
                except Exception:
                    pass
        finally:
            self._sync_widget_states()

    def _apply_entry_value_after_state(self, name: str, w: tk.Entry | ttk.Entry,
                                        var: tk.Variable, s: str) -> None:
        spec = self._entry_spec(name)
        if spec is None or not spec.placeholder_as_hint:
            setattr(w, "_tkouter_ph_active", False)
            try:
                w.configure(foreground=getattr(w, "_tkouter_fg_normal",
                                                w.cget("foreground")))
            except Exception:
                pass
            return
        ph = getattr(w, "_tkouter_placeholder", "") or ""
        try:
            fg0 = getattr(w, "_tkouter_fg_normal", w.cget("foreground"))
        except Exception:
            fg0 = getattr(w, "_tkouter_fg_normal", None)
        if not ph:
            setattr(w, "_tkouter_ph_active", False)
            try:
                if fg0 is not None:
                    w.configure(foreground=fg0)
            except Exception:
                pass
            return
        if s.strip():
            setattr(w, "_tkouter_ph_active", False)
            try:
                if fg0 is not None:
                    w.configure(foreground=fg0)
            except Exception:
                pass
            return
        setattr(w, "_tkouter_ph_active", False)
        try:
            if fg0 is not None:
                w.configure(foreground=fg0)
        except Exception:
            pass
        focus = w.focus_get()
        if focus is not None and str(focus) == str(w):
            return
        var.set(ph)
        setattr(w, "_tkouter_ph_active", True)
        try:
            w.configure(foreground="grey")
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
                try:
                    result = spec.on_update()
                    if isinstance(result, str):
                        value = result
                    elif isinstance(result, dict):
                        value = result.get(spec.name, value)
                except Exception:
                    pass
            tk_w.configure(text=str(value))  # type: ignore[call-arg]

    # ── build & run ──

    def _build_widgets(self) -> None:
        """Create tkinter widgets from registered specs."""
        if self._root is None:
            return

        for spec in self._widgets:
            master = self._widget_masters.get(spec.name, self._root)
            kind = spec.kind
            e = spec.extras

            if kind == "label":
                w = ttk.Label(master, text="", anchor="center", justify="center")
                for opt in ("font", "anchor", "justify", "padding"):
                    if opt in e:
                        w.configure(**{opt: e[opt]})
                self._tk_widgets[spec.name] = w
                if spec.on_update is not None:
                    try:
                        result = spec.on_update()
                        if isinstance(result, str):
                            w.configure(text=result)
                        elif isinstance(result, dict):
                            w.configure(text=str(list(result.values())[0]) if result else "")
                    except Exception:
                        w.configure(text="")

            elif kind == "button":
                w = ttk.Button(master, text=spec.label_text or spec.name)
                self._tk_widgets[spec.name] = w
                if spec.on_click is not None:
                    fn = spec.on_click
                    w.configure(command=lambda s=spec, f=fn: self._on_button_click(s, f))

            elif kind == "entry":
                var = tk.StringVar(value="")
                w = ttk.Entry(master, textvariable=var)
                self._tk_widgets[spec.name] = w
                self._tk_vars[spec.name] = var
                # Apply widget options from extras
                for opt in ("show", "width"):
                    if opt in e:
                        w.configure(**{opt: e[opt]})
                if spec.placeholder_as_hint and spec.placeholder:
                    ph = spec.placeholder
                    var.set(ph)
                    setattr(w, "_tkouter_ph_active", True)
                    setattr(w, "_tkouter_placeholder", ph)
                    try:
                        setattr(w, "_tkouter_fg_normal", w.cget("foreground"))
                        w.configure(foreground="grey")
                    except Exception:
                        setattr(w, "_tkouter_fg_normal", None)
                    w.bind("<FocusIn>", lambda _e, n=spec.name: self._entry_focus_in(n))
                    w.bind("<FocusOut>", lambda _e, n=spec.name: self._entry_focus_out(n))
                if spec.on_update is not None:
                    fn = spec.on_update
                    w.bind("<KeyRelease>", lambda _e, s=spec, f=fn: self._on_entry_change(s, f))

            elif kind == "checkbutton":
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

            elif kind == "radiobutton":
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

            elif kind == "text":
                w = tk.Text(master, width=e.get("width", 50), height=e.get("height", 8),
                            name=spec.name)
                self._tk_widgets[spec.name] = w
                if spec.on_update is not None:
                    fn = spec.on_update
                    w.bind("<KeyRelease>", lambda _e, s=spec, f=fn:
                           self._on_text_change(s, f))

            elif kind == "scale":
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

            elif kind == "spinbox":
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

            elif kind == "listbox":
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

            elif kind == "canvas":
                w = tk.Canvas(master, width=e.get("width", 300), height=e.get("height", 200),
                              bg=e.get("bg", "#f0f0f0"), name=spec.name)
                self._tk_widgets[spec.name] = w

            elif kind == "message":
                w = tk.Message(master, text="", name=spec.name)
                self._tk_widgets[spec.name] = w
                if e.get("width") is not None:
                    w.configure(width=e["width"])
                if e.get("auto_width", True):
                    self._bind_message_auto_width(w, master)
                if spec.on_update is not None:
                    try:
                        result = spec.on_update()
                        if isinstance(result, str):
                            w.configure(text=result)
                        elif isinstance(result, dict):
                            w.configure(text=str(list(result.values())[0]) if result else "")
                    except Exception:
                        w.configure(text="")

    # ── event handlers ──

    def _on_button_click(self, spec: WidgetSpec, fn: Any) -> None:
        try:
            values = self._entry_values_dict()
            result = fn(values)
            self._apply_state(result)
        except Exception as e:
            self._apply_state({"error": str(e)})

    def _on_entry_change(self, spec: WidgetSpec, fn: Any) -> None:
        try:
            value = self._entry_effective_value(spec.name)
            result = fn(value)
            self._apply_state(result)
        except Exception:
            pass

    def _on_checkbutton_change(self, spec: WidgetSpec, fn: Any,
                                var: tk.StringVar, key: str) -> None:
        val = var.get()
        self._state[key] = val
        try:
            result = fn(val == "1")
            self._apply_state(result)
        except Exception:
            pass

    def _on_radiobutton_change(self, spec: WidgetSpec, fn: Any,
                                var: tk.Variable, key: str) -> None:
        val = var.get()
        self._state[key] = val
        try:
            result = fn(val)
            self._apply_state(result)
        except Exception:
            pass

    def _on_var_change(self, spec: WidgetSpec, fn: Any,
                        var: tk.Variable, key: str) -> None:
        val = var.get()
        self._state[key] = val
        try:
            result = fn(val)
            self._apply_state(result)
        except Exception:
            pass

    def _on_text_change(self, spec: WidgetSpec, fn: Any) -> None:
        w = self._tk_widgets.get(spec.name)
        value = ""
        if w is not None and hasattr(w, "get"):
            value = w.get("1.0", "end-1c")  # type: ignore[attr-defined]
        try:
            result = fn(value)
            self._apply_state(result)
        except Exception:
            pass

    def _on_listbox_select(self, spec: WidgetSpec, fn: Any) -> None:
        w = self._tk_widgets.get(spec.name)
        value = ""
        if w is not None and hasattr(w, "curselection"):
            sel = w.curselection()  # type: ignore[attr-defined]
            if sel and hasattr(w, "get"):
                value = w.get(sel[0])  # type: ignore[attr-defined]
        self._state[spec.name] = value
        try:
            result = fn(value)
            self._apply_state(result)
        except Exception:
            pass

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
        from tkouter.layout import LayoutBuilder
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
        self._tk_widgets.clear()
        self._tk_vars.clear()
        self._widget_masters.clear()
        self._row_pack_jobs.clear()
        self._grid_pack_jobs.clear()

        if layout is not None:
            if isinstance(layout, list):
                from tkouter.layout import Layout
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
        self._tk_widgets.clear()
        self._tk_vars.clear()
        self._widget_masters.clear()
        self._row_pack_jobs.clear()
        self._grid_pack_jobs.clear()
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
            if w.kind == "entry":
                d["placeholder_as_hint"] = w.placeholder_as_hint
            widgets_out.append(d)
        return {"title": self._title, "widgets": widgets_out}

    @property
    def state(self) -> dict[str, Any]:
        return dict(self._state)
