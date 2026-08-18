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
import contextlib
import inspect
import os
import sys
import tkinter as tk
import tkinter.ttk as ttk
import traceback
import unicodedata
import warnings
from collections.abc import Awaitable, Callable, Generator, Mapping
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeVar

ProgressModeLike = Literal["determinate", "indeterminate"]

from nextpytk import tokens as t
from nextpytk.a11y import A11yEngine
from nextpytk.async_engine import AsyncEngine, AsyncJob
from nextpytk.schema import SchemaExporter
from nextpytk.state import StateStore
from nextpytk.widget_ops import (
    EventHandlersMixin,
    WidgetBuildersMixin,
    WidgetRegistrationMixin,
)
from nextpytk.widget_ops.decorators import (
    normalize_treeview_columns as _normalize_treeview_columns,
    validate_choice as _validate_choice,
    validate_positive_int as _validate_positive_int,
)
from nextpytk.tokens import PLACEHOLDER_FG
from nextpytk.types import (
    BindOptions,
    ButtonOptions,
    CanvasOptions,
    CheckbuttonOptions,
    ComboboxOptions,
    EntryOptions,
    EventSeq,
    FilepickerCallback,
    FilepickerOptions,
    FillLike,
    LabelOptions,
    EntryEventHandler,
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
    WrapLike,
)
from nextpytk.widgets import WidgetSpec

if TYPE_CHECKING:
    from nextpytk.layout import Layout, LayoutBuilder

# ── asyncio helper: wrapper around root.after for async scheduling ──
TkAppAfterHandle: TypeAlias = str  # root.after returns a string id

F = TypeVar("F", bound=Callable[..., Any])
NotebookTabChange = Callable[[str], dict[str, Any] | None]

from nextpytk.state.store import levenshtein as _levenshtein


# ── callback type aliases ──

# label/status: no arg, returns str or state dict
LabelCallback = Callable[[], str | dict[str, Any]]

# button: receives entry values dict (optional), returns state dict
ButtonCallback = (
    Callable[[dict[str, Any]], dict[str, Any]]
    | Callable[[], dict[str, Any]]
)
BindCallback = ButtonCallback  # bind: same signature as button

# entry / text / scale / spinbox: receives value str (optional), returns state dict
ValueCallback = Callable[[str], dict[str, Any]] | Callable[[], dict[str, Any]]

# treeview: receives selected row index (-1 if none), returns state dict
TreeviewSelectCallback = Callable[[int], dict[str, Any]]
TreeviewActivateCallback = TreeviewSelectCallback

# checkbutton: receives bool, returns state dict
BoolCallback = Callable[[bool], dict[str, Any]]


# ── decorator argument validation ──

def _validate_choice(
    options: Mapping[str, Any],
    key: str,
    *,
    allowed: tuple[str, ...],
    default: str,
    widget: str,
) -> Any:
    """Validate that ``options[key]`` is one of ``allowed``; else raise.

    Catches invalid enum-like arguments at registration time (before any Tk
    widget is built), so a mistyped value like ``wrap="wrap"`` or
    ``state="disabled"`` fails with a clear message instead of a cryptic
    ``_tkinter.TclError`` at runtime.
    """
    value = options.get(key, default)
    if value not in allowed:
        raise ValueError(
            f"invalid {key}={value!r} for {widget!r}: expected one of "
            f"{', '.join(repr(a) for a in allowed)}"
        )
    return value


def _validate_positive_int(
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


def _normalize_treeview_columns(
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
        "menubar", "filepicker",
        "add_label", "add_status", "add_message", "add_button", "add_entry",
        "add_checkbutton", "add_radiobutton", "add_text", "add_scale", "add_spinbox",
        "add_listbox", "add_combobox", "add_treeview", "add_canvas",
        "add_filepicker", "add_progressbar",
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


class TkApp(WidgetRegistrationMixin, WidgetBuildersMixin, EventHandlersMixin):
    """Tk application: register widgets as functions, declare layout separately.

    Decorators register intent; Layout provides structure. The writing style
    is Flask-inspired.
    """

    def __init__(
        self,
        title: str = "nextpytk",
        *,
        debug: bool = False,
        theme: bool | str | t.ThemeTokens = "kizashi",
        ingest_trace: bool = False,
        debug_padding: bool | None = None,
    ):
        self._title = title
        self._debug = debug
        # ``debug_padding`` defaults to off, but the ``NEXTPYTK_DEBUG_PADDING``
        # environment variable turns the padding overlay on at startup without
        # touching the app code (e.g. ``NEXTPYTK_DEBUG_PADDING=1``).
        if debug_padding is None:
            debug_padding = os.environ.get("NEXTPYTK_DEBUG_PADDING", "").strip() not in ("", "0")
        self._debug_padding = debug_padding
        self._theme, self._theme_tokens = self._normalize_theme(theme)
        self._kizashi = self._theme in ("kizashi", "kizashi-dark") or isinstance(theme, t.ThemeTokens)
        self._deferred_tcl_scripts: list[tuple[str, str | None]] = []
        self._store = StateStore(ingest_trace=ingest_trace, debug=debug)
        self._a11y = A11yEngine()
        self._widgets: list[WidgetSpec] = []
        self._root: tk.Tk | None = None
        self._tk_widgets: dict[str, tk.Widget] = {}
        self._widget_masters: dict[str, tk.Widget] = {}
        self._row_pack_jobs: list[tuple[tk.Frame, Any]] = []
        self._grid_pack_jobs: list[tuple[tk.Frame, Any]] = []
        self._view_widgets: dict[str, list[str]] = {}
        self._view_layouts: dict[str, Layout] = {}
        self._multiviews: dict[str, dict[str, Any]] = {}
        self._current_view: str | None = None
        # Swap targets (Layout.target) → their persistent frames.
        self._swap_targets: dict[str, tk.Frame] = {}
        # Swap targets → variant name → (variant frame, layout).
        self._swap_variants: dict[str, dict[str, Any]] = {}
        self._swap_frames: dict[str, dict[str, tk.Frame]] = {}
        self._swap_current: dict[str, str] = {}
        self._stages: dict[str, dict[str, Any]] = {}
        self._current_stage: str | None = None
        self._stage_container: tk.Frame | None = None
        self._async_engine = AsyncEngine()
        self._treeview_inner: dict[str, ttk.Treeview] = {}
        self._treeview_row_cache: dict[str, tuple[Any, ...]] = {}
        self._text_inner: dict[str, tk.Text] = {}
        self._text_scrollbars: dict[str, ttk.Scrollbar | None] = {}
        self._text_hscrollbars: dict[str, ttk.Scrollbar] = {}
        self._text_scroll_sync: dict[str, str] = {}
        # Widgets explicitly hidden via ``app.hide(name)`` so they are not
        # rebuilt as visible on the next sync.
        self._hidden_widgets: set[str] = set()
        # pack options captured from ``pack_info()`` at hide time, replayed by
        # ``app.show(name)`` to restore a packed widget's geometry.
        self._hidden_pack_opts: dict[str, dict[str, Any]] = {}
        # Geometry manager ("grid" | "pack") in effect when a widget was
        # hidden, so ``show()`` knows how to restore it after ``grid_remove`` /
        # ``pack_forget`` cleared ``winfo_manager``.
        self._hidden_geometry: dict[str, str] = {}
        # Pending padding changes requested via ``set_padding`` while a widget
        # was hidden. They are applied by ``show()`` when the widget returns,
        # because calling ``pack_configure`` on a ``pack_forget``'d widget
        # would re-pack (re-show) it prematurely.
        self._hidden_padding: dict[str, dict[str, Any]] = {}
        # Section frames created by Layout.section(), keyed by the section's
        # name. Used by hide_section()/show_section() to hide or reveal an
        # entire section frame (and its reserved space) at once.
        self._section_frames: dict[str, tk.Frame] = {}
        # Section names that were given explicitly via ``section(name=...)``.
        # Auto-derived names ("<first widget>_section") are registered too, but
        # only explicit names should suppress the grouped-widget badge label.
        self._explicit_section_names: set[str] = set()
        # pack options captured from section frames at hide_section() time,
        # replayed by show_section() to restore the frame's geometry.
        self._hidden_section_opts: dict[str, dict[str, Any]] = {}
        # Callables invoked after a text widget's content is replaced, keyed by
        # text widget name. Used by paired line-number gutters to stay in sync.
        self._text_set_hooks: dict[str, list[Callable[[], None]]] = {}
        self._paned_inner: dict[str, ttk.Panedwindow] = {}
        self._pane_frames: dict[str, tk.Widget] = {}
        self._layout_paned_opts: dict[str, dict[str, Any]] = {}
        self._current_pane: str | None = None
        # The outermost content_frame (page-margin wrapper) created when a
        # top-level layout is mounted; used to update the page margin at runtime.
        self._content_frame: ttk.Frame | None = None
        self._menubar_submenus: dict[str | int, list[tk.Menu | None]] = {}
        self._declared_state_keys: set[str] = set()
        self._warned_state_keys: set[str] = set()
        self._first_focusable: tk.Widget | None = None
        self._debug_padding_badges: list[tk.Label] = []
        # (x, y) slots already occupied by a padding badge, so overlapping
        # badges are nudged down onto their own line.
        self._debug_badge_rows: set[tuple[int, int]] = set()
        # The root <Configure> handler that re-places badges on resize while
        # the debug-padding overlay is active (None when off).
        self._debug_padding_rebind: str | None = None
        # Badges for the debug-layout overlay (each widget's debug_layout()
        # info rendered at its own location).
        self._debug_layout_badges: list[tk.Label] = []
        self._debug_layout_rebind: str | None = None
        # Periodic (1s) poll that re-places badges when widget geometry moves.
        self._debug_overlay_poll_job: str | None = None
        # Last-seen widget root coordinates, to only rebuild on real movement.
        self._debug_overlay_last_pos: dict[str, tuple[int, int]] = {}
        self._register_default_builders()

    def _normalize_theme(
        self,
        theme: bool | str | t.ThemeTokens,
    ) -> tuple[str, t.ThemeTokens]:
        """Normalize theme argument to (theme_name, ThemeTokens)."""
        if isinstance(theme, t.ThemeTokens):
            return theme.name, theme
        if isinstance(theme, bool):
            warnings.warn(
                "theme=True/False is deprecated; use theme='kizashi' or "
                "theme='none' (bool support will be removed in v0.5.0).",
                DeprecationWarning,
                stacklevel=3,
            )
            return ("kizashi", t.KIZASHI_LIGHT) if theme else ("none", t.KIZASHI_LIGHT)
        if isinstance(theme, str):
            if theme == "kizashi":
                return "kizashi", t.KIZASHI_LIGHT
            if theme == "kizashi-dark":
                return "kizashi-dark", t.KIZASHI_DARK
            return theme, t.KIZASHI_LIGHT
        raise TypeError(f"theme must be bool, str, or ThemeTokens, got {type(theme).__name__}")

    def clear_runtime(self) -> None:
        self._tk_widgets.clear()
        self._treeview_inner.clear()
        self._treeview_row_cache.clear()
        self._paned_inner.clear()
        self._pane_frames.clear()
        self._layout_paned_opts.clear()
        self._current_pane = None
        self._content_frame = None
        self._tk_vars.clear()
        self._widget_masters.clear()
        self._row_pack_jobs.clear()
        self._grid_pack_jobs.clear()
        self._menubar_submenus.clear()
        self._text_inner.clear()
        self._text_scrollbars.clear()
        self._text_scroll_sync.clear()
        self._text_set_hooks.clear()
        self._hidden_widgets.clear()
        self._hidden_pack_opts.clear()
        self._hidden_geometry.clear()
        self._hidden_padding.clear()
        self._section_frames.clear()
        self._explicit_section_names.clear()
        self._hidden_section_opts.clear()
        self._debug_padding_badges.clear()
        self._debug_badge_rows.clear()
        self._debug_padding_rebind = None
        self._debug_layout_badges.clear()
        self._debug_layout_rebind = None
        self._debug_overlay_poll_job = None
        self._debug_overlay_last_pos = {}
        self._a11y.last_toggles.clear()
        self._pending_ingest.clear()
        self._ingest_flush_job = None
        self._syncing_var_keys.clear()
        self._current_view = None
        self._current_stage = None
        self._swap_targets.clear()
        self._swap_frames.clear()
        self._swap_current.clear()
        self._first_focusable = None

    def pane(self, pane_id: str) -> _PaneContext:
        """Context manager: register following widgets inside a ``@app.paned`` pane."""
        return _PaneContext(self, pane_id)

    def _add_spec(self, spec: WidgetSpec) -> None:
        """Register a WidgetSpec, replacing any existing spec with the same name.

        Re-registering a name (e.g. re-decorating ``@app.button("next")`` in an
        interactive session) silently replaces the previous spec in place, so
        the latest definition wins. ``bind`` specs are exempt from replacement
        checks: a bind sharing a button's name is the documented pairing for
        shortcut annotation, and a bind never replaces a widget spec.
        """
        if spec.kind != "bind":
            for i, w in enumerate(self._widgets):
                if w.name == spec.name and w.kind != "bind":
                    self._widgets[i] = spec
                    return
        self._widgets.append(spec)

    def unregister(self, name: str) -> bool:
        """Remove a registered widget spec by name.

        Returns ``True`` if a spec was removed, ``False`` if no widget with
        that name was registered. This is useful in interactive sessions to
        drop a widget (and its callback) before ``run()``, e.g. to re-declare
        it with a different kind or options.

        Only the spec is removed; if the widget was already built, the live
        Tk widget is left in place. Call ``unregister`` before ``run()`` /
        ``build_widgets()`` to affect the built layout.
        """
        for i, w in enumerate(self._widgets):
            if w.name == name:
                del self._widgets[i]
                return True
        return False

    @staticmethod
    def _callback_accepts_args(fn: Callable[..., Any]) -> bool:
        """Return True if ``fn`` can take positional arguments.

        Optional parameters (``values=None``) and ``*args`` count as accepting
        args; only a zero-parameter callable is invoked with no framework args.
        """
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return True
        return any(
            p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
            for p in sig.parameters.values()
        )

    def _dispatch(self, spec_name: str, fn: Callable[..., Any],
                  *args: Any) -> Any:
        """Run a user callback under the framework error policy.

        Callbacks may omit unused arguments (e.g. ``def on_click(): ...`` for
        a button). If the callable declares any positional parameter
        (including defaults or ``*args``), the usual framework args are passed.

        Exceptions are never swallowed silently: the traceback always goes
        to stderr, and ``TkApp(debug=True)`` re-raises.
        Returns the callback result, or ``None`` after a handled error.
        """
        try:
            if args and not self._callback_accepts_args(fn):
                return fn()
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
        widget_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Merge layout pane id and optional ``takefocus`` into widget extras."""
        out = dict(extras or {})
        if takefocus is not None:
            out["takefocus"] = takefocus
        if widget_kwargs:
            out["widget_kwargs"] = widget_kwargs
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

    def _apply_widget_overrides(self, spec: WidgetSpec) -> None:
        """Apply per-widget ``widget_kwargs`` design-token overrides.

        ``widget_kwargs`` lets apps override individual design tokens (color,
        padding, font, …) on a single widget without monkey-patching the
        shared ``tokens`` module. Keys must be options the widget accepts.
        """
        overrides = spec.extras.get("widget_kwargs")
        if not overrides:
            return
        w = self._takefocus_widget(spec)
        if w is None:
            return
        try:
            w.configure(overrides)
        except tk.TclError:
            # A bad option/name is surfaced only when the widget rejects it;
            # ignore TclError so one invalid key does not abort the build.
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
        """Apply the configured theme and window chrome to ``root``."""
        if self._deferred_tcl_scripts:
            for script_or_path, theme_name in self._deferred_tcl_scripts:
                content: str
                if os.path.isfile(script_or_path):
                    with open(script_or_path, "r", encoding="utf-8") as f:
                        content = f.read()
                else:
                    content = script_or_path
                root.tk.eval(content)
                if theme_name:
                    self._theme = theme_name
                    self._kizashi = False

        if self._theme == "none":
            return
        from nextpytk.theme import _set_windows_dpi_aware, configure_window
        _set_windows_dpi_aware()
        if self._kizashi:
            from nextpytk.theme import apply_theme
            apply_theme(root, self._theme_tokens)
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
        configure_window(root, title=self._title, tokens=self._theme_tokens)

    def set_root(self, root: tk.Tk) -> None:
        self._root = root
        self._configure_theme(root)

    def set_widget_master(self, widget_name: str, master: tk.Widget) -> None:
        self._widget_masters[widget_name] = master

    def register_swap_target(self, name: str, frame: tk.Frame) -> None:
        """Register a swap-target frame (called by ``Layout.target``)."""
        self._swap_targets[name] = frame

    def swap(
        self,
        name: str,
        *,
        variants: dict[str, object],
        default: str | None = None,
        key: str | None = None,
    ) -> Callable[[F], F]:
        """Declare runtime-swappable variants for a ``Layout.target`` region.

        Mirrors HTMX ``hx-swap``: the named target (declared via
        ``Layout().target(name)``) shows exactly one of ``variants`` at a
        time. Variants are mounted up-front and shown/hidden on demand, so
        widget state (e.g. a treeview selection or scroll position) survives
        switching.

        ``variants``: ``{name: layout_or_list}`` where each value is a
        ``Layout`` or a list of widget names (``Layout.from_list``).
        ``default``: variant shown first; ``variants.keys()`` in order
        otherwise.
        ``key``: optional state key. When ``apply_state`` updates this key,
        the target swaps to the matching variant (state-driven swap).

        Use ``app.swap(name, variant)`` to switch imperatively at runtime.

        Example::

            @app.swap(
                "main",
                variants={
                    "dir":  [Layout().section("dir_tree")],
                    "file": [Layout().paired("left", "right")],
                },
                default="dir",
                key="mode",
            )
            def main_area():
                pass
        """
        from nextpytk.layout import Layout as LayoutCls

        normalized: dict[str, Any] = {}
        for vname, value in variants.items():
            if isinstance(value, list):
                # A list is either [Layout] (a ready-made variant layout) or
                # [widget1, widget2, ...] (converted via Layout.from_list).
                if value and all(hasattr(x, "_blocks") for x in value):
                    combined = LayoutCls()
                    for layout in value:
                        combined._blocks.extend(layout._blocks)
                    normalized[vname] = combined
                else:
                    normalized[vname] = LayoutCls.from_list(value)
            else:
                normalized[vname] = value
        if default is None:
            default = next(iter(normalized), None)
        self._swap_variants[name] = {
            "variants": normalized,
            "default": default,
            "key": key,
        }

        def decorator(fn: F) -> F:
            return fn

        return decorator

    def swap_view(self, name: str, variant: str) -> None:
        """Switch the ``Layout.target`` region ``name`` to the given variant."""
        self._swap_current[name] = variant
        if self._swap_targets.get(name) is None:
            # Not yet mounted (layout not built); the variant will be shown at
            # build time.
            return
        self._render_swap(name, variant)

    def _build_swap_variants(self) -> None:
        """Mount variant frames into each swap target (called before widgets).

        Creates the persistent variant sub-frames, mounts each variant's
        section frames inside it, and registers the widget→frame mapping so
        ``build_widgets`` places each widget into its own variant section
        (not the root). The pack jobs are stored for ``_pack_swap_variants``.
        """
        self._swap_pack_jobs: dict[str, dict[str, Any]] = {}
        for name, cfg in self._swap_variants.items():
            target = self._swap_targets.get(name)
            if target is None:
                continue
            variants = cfg["variants"]
            frames: dict[str, tk.Frame] = {}
            pack_jobs: dict[str, Any] = {}
            for vname, layout in variants.items():
                vframe = tk.Frame(target, name=f"swapvar_{vname}",
                                  bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
                vframe.pack(fill="both", expand=True)
                allowed = set(layout.widget_names())
                row_jobs, grid_jobs = layout.mount_frames_into(
                    self, vframe, allowed_widgets=allowed
                )
                frames[vname] = vframe
                pack_jobs[vname] = (row_jobs, grid_jobs)
            self._swap_frames[name] = frames
            self._swap_pack_jobs[name] = pack_jobs
            default = cfg["default"]
            self._swap_current.setdefault(name, default)

    def _pack_swap_variants(self) -> None:
        """Pack/grid variant children into their frames (called after widgets).

        ``build_widgets`` has now constructed every widget under its variant
        section frame (via the mapping set by ``_build_swap_variants``).
        This packs the section children and shows the default variant.
        """
        for name, cfg in self._swap_variants.items():
            pack_jobs = self._swap_pack_jobs.get(name)
            if not pack_jobs:
                continue
            for vname, layout in cfg["variants"].items():
                row_jobs, grid_jobs = pack_jobs[vname]
                layout.pack_children_for(self, row_jobs, grid_jobs)
            default = cfg["default"]
            current = self._swap_current.get(name)
            target_variant = current if current in cfg["variants"] else default
            if target_variant is not None:
                self._render_swap(name, target_variant)

    def _render_swap(self, name: str, variant: str) -> None:
        """Show the requested variant frame; hide all others.

        ``pack_forget`` on a hidden variant frame unmaps its whole subtree, so
        we only pack/unpack the variant frames themselves. Children stay put
        and reappear automatically when the variant frame is packed again.
        """
        frames = self._swap_frames.get(name)
        if not frames:
            return
        target = self._swap_targets.get(name)
        if target is None:
            return
        for vname, vframe in frames.items():
            if vname == variant:
                vframe.pack(fill="both", expand=True)
            else:
                vframe.pack_forget()
        self._swap_current[name] = variant
        try:
            target.update_idletasks()
        except tk.TclError:
            pass

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
        """Return the underlying Tkinter/ttk widget instance for *name*, or ``None``.

        This serves as an escape hatch when you need to access raw Tkinter or
        ttk APIs directly (e.g. custom event bindings, direct item manipulation,
        custom tag configurations, or third-party controls). Returns ``None`` if
        widgets have not been built yet.
        """
        return self._tk_widgets.get(name)

    def get_widget(self, name: str) -> tk.Widget | None:
        """Alias for :meth:`widget`."""
        return self.widget(name)

    def hide(self, name: str) -> None:
        """Hide a built widget, keeping its layout geometry.

        The widget is removed from its section via ``grid_remove`` /
        ``pack_forget`` and remembered in ``self._hidden_widgets`` so a later
        ``apply_state`` sync does not repack it. Call ``app.show(name)`` to
        restore it. Safe to call when the widget is already hidden or not yet
        built (it is merely remembered).
        """
        self._hidden_widgets.add(name)
        w = self._tk_widgets.get(name)
        if w is None:
            return
        if w.winfo_manager() == "grid":
            # grid_remove preserves the original grid options internally, so
            # show() only needs to call grid() again.
            self._hidden_geometry[name] = "grid"
            w.grid_remove()
        else:
            self._hidden_geometry[name] = "pack"
            try:
                self._hidden_pack_opts[name] = dict(w.pack_info())
            except tk.TclError:
                pass
            w.pack_forget()
        # Visibility changed; re-place any active debug-overlay badges at the
        # widget's final (post-idle) position. No-op when no overlay is shown.
        self.refresh_debug_overlay()

    def show(self, name: str) -> None:
        """Restore a widget previously hidden with ``app.hide(name)``.

        Repacks the widget into its section frame. ``grid_remove`` preserves
        the original grid options, so a widget hidden while gridded returns
        to its exact cell. A widget that was ``pack``ed is re-packed with the
        same side/fill/expand it had at hide time. Safe to call when the
        widget is already visible.
        """
        self._hidden_widgets.discard(name)
        w = self._tk_widgets.get(name)
        if w is None:
            return
        if w.winfo_manager() == "grid":
            # grid_remove kept the geometry; just restore.
            w.grid()
            return
        if w.winfo_manager() == "pack":
            return
        manager = self._hidden_geometry.pop(name, None)
        if manager == "grid":
            # grid_remove left the cell options in place; grid() restores it.
            w.grid()
            return
        opts = self._hidden_pack_opts.pop(name, None)
        if opts is None:
            # A widget hidden without pack options (grid path) still needs any
            # remembered padding applied once it is gridded again.
            pending = self._hidden_padding.pop(name, None)
            if pending and w.winfo_manager() == "grid":
                w.grid_configure(**pending)
            return
        # pack_info() returns option keys with trailing underscores; strip
        # them so they are accepted by pack().
        clean = {k.rstrip("_"): v for k, v in opts.items()}
        w.pack(**clean)
        # Apply padding requested while the widget was hidden.
        pending = self._hidden_padding.pop(name, None)
        if pending and w.winfo_manager() == "pack":
            w.pack_configure(**pending)
        # Visibility changed; re-place any active debug-overlay badges at the
        # widget's final (post-idle) position. No-op when no overlay is shown.
        self.refresh_debug_overlay()

    def hide_section(self, name: str) -> None:
        """Hide the section frame that ``name`` refers to.

        ``name`` is the section label given via ``section(name=...)``. Unlike
        ``app.hide(name)`` which removes a widget from its section, this
        removes the entire section frame — including the empty vertical space
        it reserved. The original pack options are remembered so
        ``show_section(name)`` restores it exactly.

        Only ``pack``-managed section frames are supported (the default for
        ``Layout.section()``). A section whose frame is managed by another
        geometry manager is left untouched. Calling this with an unknown
        ``name`` (or a section that is already hidden) is a no-op.
        """
        frame = self._section_frames.get(name)
        if frame is None:
            return
        if frame.winfo_manager() != "pack":
            return
        try:
            self._hidden_section_opts[name] = dict(frame.pack_info())
        except tk.TclError:
            return
        frame.pack_forget()
        # Visibility changed; re-place any active debug-overlay badges.
        self.refresh_debug_overlay()

    def show_section(self, name: str) -> None:
        """Restore a section frame previously hidden with ``hide_section``.

        Re-packs the section frame with the same side/fill/expand/padding it
        had when it was hidden. Calling this with an unknown ``name``, or for a
        section that was not hidden (or is not ``pack``-managed), is a no-op.
        """
        frame = self._section_frames.get(name)
        if frame is None:
            return
        # Already visible / not hidden; nothing to restore.
        if frame.winfo_manager() == "pack":
            return
        opts = self._hidden_section_opts.pop(name, None)
        if opts is None:
            return
        # pack_info() returns option keys with trailing underscores; strip
        # them so they are accepted by pack().
        clean = {k.rstrip("_"): v for k, v in opts.items()}
        frame.pack(**clean)
        # Visibility changed; re-place any active debug-overlay badges.
        self.refresh_debug_overlay()

    def is_visible(self, name: str) -> bool:
        """Return True if the named widget is currently mapped (not hidden)."""
        w = self._tk_widgets.get(name)
        if w is None:
            return False
        return w.winfo_manager() in ("pack", "grid", "place")

    def set_padding(
        self,
        name: str,
        *,
        padx: int | tuple[int, int] | None = None,
        pady: int | tuple[int, int] | None = None,
    ) -> None:
        """Dynamically change a built widget's layout padding, hide-aware.

        ``padx``/``pady`` mirror the ``pack`` padding options. Only the
        padding is changed; side/fill/expand/position are left untouched.

        When the widget is currently visible it is applied immediately. When
        it is hidden (see :meth:`hide`) the change is remembered and applied
        when :meth:`show` restores the widget. This avoids the classic Tk
        pitfall where calling ``pack_configure`` on a ``pack_forget``'d
        widget silently re-packs (re-shows) it.

        Works for ``grid``-managed widgets too: the new padding is applied via
        ``grid_configure``.
        """
        w = self._tk_widgets.get(name)
        if w is None:
            return
        # Remember the request regardless, so a change made while hidden is
        # applied on show(). Only store the options that were actually given.
        pending: dict[str, Any] = {}
        if padx is not None:
            pending["padx"] = padx
        if pady is not None:
            pending["pady"] = pady
        if pending:
            self._hidden_padding[name] = pending

        if w.winfo_manager() == "grid":
            w.grid_configure(**pending)
        elif w.winfo_manager() == "pack":
            w.pack_configure(**pending)
        # Else (hidden / not yet packed): keep the remembered value; show()
        # applies it.

    def set_page_margin(self, margin: int) -> None:
        """Update the outer page margin (``content_frame`` padding) at runtime.

        The outermost page pad defaults to ``SPACE[6]`` (24px), or whatever
        ``Layout(page_margin=...)`` set. Use this to re-scale it dynamically
        (e.g. proportionally to window height in a resize handler). It is a
        no-op when the app has not mounted a top-level ``content_frame``.
        """
        frame = self._content_frame
        if frame is None or not bool(frame.winfo_exists()):
            return
        try:
            frame.configure(padding=margin)
        except tk.TclError:
            pass

    def widget_padding(self, name: str) -> dict[str, Any]:
        """Return the current layout padding of a built widget.

        Reads ``pack_info()`` / ``grid_info()`` and reports the padding as
        ``{"padx": ..., "pady": ...}``. Values are normalized to the
        ``(left, right)`` / ``(top, bottom)`` form where possible so callers
        (and the padding debug overlay) get a stable shape. Returns ``{}``
        when the widget is not built or not managed.
        """
        w = self._tk_widgets.get(name)
        if w is None or not bool(w.winfo_exists()):
            return {}
        try:
            mgr = w.winfo_manager()
            if mgr == "pack":
                pi = w.pack_info()
                padx, pady = pi.get("padx"), pi.get("pady")
            elif mgr == "grid":
                gi = w.grid_info()
                padx, pady = gi.get("padx"), gi.get("pady")
            else:
                return {}
        except tk.TclError:
            return {}
        return {"padx": padx, "pady": pady}

    def show_debug_padding(self, on: bool = True) -> None:
        """Overlay layout frames and widgets with badges showing their padding.

        Three kinds of padding are surfaced, each with its own badge color:

        - **Section-frame outer padding** (yellow): the ``padx``/``pady`` a
          ``Layout.section()`` / ``frame()`` packs its frame with.
        - **Widget outer padding** (cyan): the ``padx``/``pady`` a built widget
          itself is packed/gridded with (e.g. set via ``pack_configure`` or
          ``set_padding``).
        - **Widget inner padding** (orange): a label's ``padding`` option or a
          text widget's ``padx``/``pady``.

        Toggle off with ``show_debug_padding(False)``. When ``debug_padding=True``
        is passed to the constructor, the overlay is enabled automatically at
        startup. The badges are ``place``-managed labels over the root, so they
        never disturb the pack/grid layout itself.
        """
        root = self._root
        if root is None:
            return
        # Remove any existing badges first (idempotent toggle).
        self._hide_debug_padding_badges()
        self._debug_badge_rows.clear()
        # Drop any resize re-render binding.
        self._unbind_debug_padding_resize()
        if not on:
            if self._debug_layout_rebind is None:
                self._cancel_debug_overlay_poll()
            return

        self._build_padding_badges()
        self._bind_debug_padding_resize()
        self._ensure_debug_overlay_poll()

    def refresh_debug_overlay(self) -> None:
        """Re-read and re-place any active debug overlay badges.

        The resize-triggered re-render only fires when the window size actually
        changes, so dynamic layout changes that do not resize the window (e.g.
        hiding/showing a widget, swapping a region) leave the badges stale.
        Call this after such a change to force the padding and/or debug-layout
        badges to re-read live geometry. It is a no-op when neither overlay is
        active.

        Rebuilding is deferred to ``after_idle`` so the badges are placed at
        the widget's *final* positions. ``pack``/``grid`` settle their geometry
        in an idle task, so reading positions synchronously right after
        ``show()``/``hide()`` would capture stale coordinates.
        """
        root = self._root
        if root is None:
            return
        if self._debug_padding_rebind is None and self._debug_layout_rebind is None:
            return

        def _rebuild() -> None:
            if self._debug_padding_rebind is not None:
                self._build_padding_badges()
            if self._debug_layout_rebind is not None:
                self._build_debug_layout_badges()

        try:
            root.after_idle(_rebuild)
        except tk.TclError:
            pass

    def _ensure_debug_overlay_poll(self) -> None:
        """Start a 1s poll that re-places badges when any widget's position moves.

        Some layout shifts (e.g. a container resizing its children, a custom
        ``<Configure>`` handler) are not surfaced to the framework's own
        hooks, so the badges can drift. Polling every second and rebuilding
        only when a widget's root coordinates actually changed keeps them in
        sync without the flicker of a constant rebuild.
        """
        root = self._root
        if root is None:
            return
        if self._debug_overlay_poll_job is not None:
            return
        if self._debug_padding_rebind is None and self._debug_layout_rebind is None:
            return

        def _poll() -> None:
            # Only keep polling while at least one overlay is active.
            if self._debug_padding_rebind is None and self._debug_layout_rebind is None:
                self._debug_overlay_poll_job = None
                return
            moved = self._debug_overlay_widgets_moved()
            if moved:
                if self._debug_padding_rebind is not None:
                    self._build_padding_badges()
                if self._debug_layout_rebind is not None:
                    self._build_debug_layout_badges()
            try:
                self._debug_overlay_poll_job = root.after(1000, _poll)
            except tk.TclError:
                self._debug_overlay_poll_job = None

        try:
            self._debug_overlay_poll_job = root.after(1000, _poll)
        except tk.TclError:
            self._debug_overlay_poll_job = None

    def _debug_overlay_widgets_moved(self) -> bool:
        """Return True if any badge-relevant widget moved since last check."""
        moved = False
        pos: dict[str, tuple[int, int]] = {}
        for spec in self._widgets:
            if spec.name in self._hidden_widgets:
                continue
            w = self._tk_widgets.get(spec.name)
            if w is None or not bool(w.winfo_exists()):
                continue
            try:
                key = (w.winfo_rootx(), w.winfo_rooty())
            except tk.TclError:
                continue
            pos[spec.name] = key
            if self._debug_overlay_last_pos.get(spec.name) != key:
                moved = True
        self._debug_overlay_last_pos = pos
        return moved

    def _cancel_debug_overlay_poll(self) -> None:
        """Cancel the periodic poll (if running)."""
        root = self._root
        job = self._debug_overlay_poll_job
        self._debug_overlay_poll_job = None
        if root is not None and job is not None:
            try:
                root.after_cancel(job)
            except tk.TclError:
                pass

    def _build_padding_badges(self) -> None:
        """(Re)build the padding badges from the current widget state.

        Position and padding values are read live, so calling this again after
        a resize or ``set_padding`` reflects the new values. Badges are
        cleared first (see :meth:`_hide_debug_padding_badges`).
        """
        root = self._root
        if root is None:
            return
        self._hide_debug_padding_badges()
        self._debug_badge_rows.clear()

        # 0) Page margin (outermost content_frame). Show its padding as a badge
        # labelled "page" so the outer safe area is visible. Normalize a
        # uniform padding tuple (e.g. (8,)) to a single value for a clean badge.
        content = self._content_frame
        if content is not None and bool(content.winfo_exists()):
            try:
                pm = content.cget("padding")
            except tk.TclError:
                pm = None
            if pm:
                pmv = self._normalize_padding_display(pm)
                self._debug_padding_badges.append(self._make_padding_badge(
                    root, content, pmv, pmv, bg="#c8e6c9", label="page",
                ))

        # 1) Distinct section frames that own widgets → their outer padding.
        # Build a frame → owning-widget-names map so the badge can show which
        # widgets a section groups together. Only visible widgets are included,
        # so a section whose every widget is hidden (e.g. a code block on a
        # no-code slide) does not keep a stale badge.
        def _is_hidden(name: str) -> bool:
            if name in self._hidden_widgets:
                return True
            w = self._tk_widgets.get(name)
            if w is None or not bool(w.winfo_exists()):
                return True
            # In multiview / stages the inactive tabs' widgets exist but are
            # not mapped (pack_forget), so they must not receive badges. Only
            # apply this when the root itself is mapped: headless tests use a
            # withdrawn root, where every widget reports unmapped.
            try:
                if root.winfo_ismapped() and not bool(w.winfo_ismapped()):
                    return True
            except tk.TclError:
                pass
            return False

        # Map each section frame id → its explicit section() name, when one was
        # given. Auto-derived names ("<first>_section") are excluded so a
        # multi-widget section without an explicit name still reports the
        # grouped widget names on its badge.
        section_name_by_frame: dict[int, str] = {
            id(frame): name
            for name, frame in self._section_frames.items()
            if name in self._explicit_section_names
        }

        frame_names: dict[int, list[str]] = {}
        for spec in self._widgets:
            frame = self._widget_masters.get(spec.name)
            if frame is None or not bool(frame.winfo_exists()):
                continue
            if _is_hidden(spec.name):
                continue
            frame_names.setdefault(id(frame), []).append(spec.name)
        seen_frames: list[tk.Widget] = []
        for spec in self._widgets:
            frame = self._widget_masters.get(spec.name)
            if frame is None or not bool(frame.winfo_exists()):
                continue
            if _is_hidden(spec.name):
                continue
            if frame not in seen_frames:
                seen_frames.append(frame)
        for frame in seen_frames:
            padx, pady = self._frame_padding(frame)
            if not padx and not pady:
                continue
            # Prefer the explicit section name for a clear badge; otherwise
            # fall back to the widget names the section groups. This keeps
            # ``section[diagram_section]`` distinct from ``widget[diagram]``.
            section = section_name_by_frame.get(id(frame))
            if section is None:
                section = ",".join(frame_names.get(id(frame), []))
            if not section:
                # Every widget in this section is hidden; do not badge it.
                continue
            self._debug_padding_badges.append(self._make_padding_badge(
                root, frame, padx, pady, bg="#ffd54d", label="section",
                name=section,
            ))

        # 2) Each built widget's own outer padding + inner padding.
        for spec in self._widgets:
            if _is_hidden(spec.name):
                continue
            w = self._tk_widgets.get(spec.name)
            if w is None or not bool(w.winfo_exists()):
                continue
            opx, opy = self._frame_padding(w)
            if opx or opy:
                self._debug_padding_badges.append(self._make_padding_badge(
                    root, w, opx, opy, bg="#4dd0ff", label="widget",
                    name=spec.name,
                ))
            ipx, ipy = self._widget_inner_padding(spec, w)
            if ipx or ipy:
                # For text widgets the inner padx/pady sits the first character
                # at (padx, pady) inside the widget, so align the inner badge
                # with that first character's top-left corner. For labels,
                # fall back to just inside the widget.
                if spec.kind == "text":
                    dx = self._inner_offset(ipx)
                    dy = self._inner_offset(ipy)
                else:
                    dx = 0
                    dy = max(0, (w.winfo_height() or 0) - 20)
                self._debug_padding_badges.append(self._make_padding_badge(
                    root, w, ipx, ipy, bg="#ff9d4d", label="inner",
                    name=spec.name, dx=dx, dy=dy,
                ))

    def _place_badge(self, badge: tk.Label, x: int, y: int) -> None:
        """Place a badge, nudging it down if another badge already occupies (x,y).

        Section frames and the widgets inside them share nearly the same
        top-left corner, so section/self/inner badges would otherwise stack on
        top of each other. This keeps a per-row occupancy map so every badge
        lands on its own line.
        """
        while (x, y) in self._debug_badge_rows:
            y += 18
        self._debug_badge_rows.add((x, y))
        badge.place(x=x, y=y)
        # Raise the badge above the pack/grid content. Badges are ``place``-ed
        # on the root after the content frames already exist, so without an
        # explicit lift() they can end up beneath the widgets and stay hidden.
        # Only the click handler used to lift() them; doing it here too keeps
        # every badge visible from the start.
        try:
            badge.lift()
        except tk.TclError:
            pass

    def _widget_inner_padding(
        self,
        spec: WidgetSpec,
        w: tk.Widget,
    ) -> tuple[Any, Any]:
        """Return a widget's own inner padding (label padding / text padx,pady).

        For ``text`` widgets the inner ``tk.Text`` lives in ``_text_inner``,
        not the container frame in ``w``, so it is queried directly.
        """
        if spec.kind == "text":
            inner = self._text_inner.get(spec.name)
            if inner is not None and bool(inner.winfo_exists()):
                try:
                    return inner.cget("padx"), inner.cget("pady")
                except tk.TclError:
                    return None, None
            return None, None
        try:
            cls = w.winfo_class()
            if cls in ("TLabel", "Label"):
                p = w.cget("padding")
                if p:
                    if isinstance(p, (tuple, list)):
                        return p, None
                    return p, p
        except tk.TclError:
            pass
        return None, None

    @staticmethod
    def _inner_offset(v: Any) -> int:
        """Return a pixel offset from an inner-padding value.

        ``tk.Text``'s ``padx``/``pady`` are plain ints; a ``(left, top, ...)``
        tuple (label ``padding``) uses its leading element. Anything else
        (e.g. ``None``, a string) maps to 0.
        """
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, (tuple, list)):
            if v and isinstance(v[0], (int, float)):
                return int(v[0])
        return 0

    def _frame_padding(self, frame: tk.Widget) -> tuple[Any, Any]:
        """Return the (padx, pady) a layout frame is packed/gridded with."""
        try:
            mgr = frame.winfo_manager()
            if mgr == "pack":
                pi = frame.pack_info()
                return pi.get("padx"), pi.get("pady")
            if mgr == "grid":
                gi = frame.grid_info()
                return gi.get("padx"), gi.get("pady")
        except tk.TclError:
            pass
        return None, None

    @staticmethod
    def _normalize_padding_display(v: Any) -> Any:
        """Collapse a uniform padding tuple like ``(8,)`` to the single value.

        ``ttk.Frame`` returns ``padding`` as a tuple; if every element is the
        same (uniform margin) we show just that number in a badge.
        """
        if isinstance(v, (tuple, list)):
            if v and all(x == v[0] for x in v):
                return v[0]
        return v

    def _make_padding_badge(
        self,
        root: tk.Misc,
        widget: tk.Widget,
        padx: Any,
        pady: Any,
        *,
        bg: str,
        label: str,
        name: str = "",
        dx: int = 0,
        dy: int = 0,
    ) -> tk.Label:
        """Create a small colored label placed at the widget's top-left corner.

        ``name`` (optional) is shown after the label so a section badge can
        report which widget(s) it groups. ``dx``/``dy`` nudge the badge right /
        down from the widget's top-left; see :meth:`_place_badge` for the
        automatic collision-free placement used here.

        When the widget is ``pack``-managed, its ``side`` / ``fill`` /
        ``expand`` are appended (single line) so the badge doubles as a
        compact layout hint.
        """
        text = f"{label} padx {padx} / pady {pady}"
        if name:
            text = f"{label}[{name}] padx {padx} / pady {pady}"
        try:
            mgr = widget.winfo_manager()
        except tk.TclError:
            mgr = None
        if mgr == "pack":
            try:
                pi = widget.pack_info()
                # Keep this on a single line. With multiple lines (\n),
                # _place_badge would read the badge's height as 1 before it is
                # placed, so the row pitch would stay 18px and multi-line
                # badges would overlap. A single line is stable.
                side = pi.get("side") or "?"
                fill = pi.get("fill") or "?"
                expand = bool(pi.get("expand"))
                anchor = pi.get("anchor") or "?"
                text += (f" / side {side} / fill {fill} / expand {expand}"
                         f" / anchor {anchor}")
            except tk.TclError:
                pass
        badge = tk.Label(
            root,
            text=text,
            bg=bg,
            fg="#000000",
            relief="solid",
            borderwidth=1,
            # Use the app font rather than a raw "TkDefaultFont" tuple, which
            # Tk would treat as a literal family name and render poorly.
            font=t.font("small"),
        )
        # Clicking a badge lifts it to the front (topmost z-order) so a badge
        # buried under another overlay is easy to read.
        badge.bind("<Button-1>", lambda _e: badge.lift())
        try:
            wx = widget.winfo_rootx()
            wy = widget.winfo_rooty()
            rrx = root.winfo_rootx()
            rry = root.winfo_rooty()
            self._place_badge(badge, wx - rrx + dx, wy - rry + dy)
        except tk.TclError:
            pass
        return badge

    def _hide_debug_padding_badges(self) -> None:
        """Destroy any previously created padding badges."""
        for b in self._debug_padding_badges:
            try:
                b.destroy()
            except tk.TclError:
                pass
        self._debug_padding_badges.clear()

    def _bind_debug_padding_resize(self) -> None:
        """Re-place badges on window resize while the overlay is active.

        Layout padding can change on resize (e.g. ``talk_slides.py`` scales
        ``set_padding`` with window height), so the badges must be re-read
        live instead of keeping a stale snapshot.

        ``<Configure>`` fires very often (moves, layout changes from
        hide/show, focus, …) — not just real resizes. Rebuilding badges on
        every event would destroy and recreate them constantly, causing
        visible flicker. So we only rebuild when the window's width or height
        actually changed, and we debounce consecutive changes through a single
        ``after`` so a resize storm settles into one rebuild.
        """
        root = self._root
        if root is None:
            return
        if self._debug_padding_rebind is not None:
            return

        last = {"w": root.winfo_width(), "h": root.winfo_height()}
        pending: dict[str, str | None] = {"job": None}

        def _rerender(_event=None) -> None:
            w = root.winfo_width()
            h = root.winfo_height()
            if w == last["w"] and h == last["h"]:
                return
            last["w"], last["h"] = w, h
            if pending["job"] is not None:
                try:
                    root.after_cancel(pending["job"])
                except tk.TclError:
                    pass
            pending["job"] = root.after(60, self._build_padding_badges)

        self._debug_padding_rebind = root.bind("<Configure>", _rerender, add="+")

    def _unbind_debug_padding_resize(self) -> None:
        """Remove the resize re-render binding (if any)."""
        root = self._root
        if root is None or self._debug_padding_rebind is None:
            return
        try:
            root.unbind("<Configure>", self._debug_padding_rebind)
        except tk.TclError:
            pass
        self._debug_padding_rebind = None

    def show_debug_layout(self, on: bool = True) -> None:
        """Overlay each widget with a badge showing its ``debug_layout()`` info.

        This is the visual, in-window counterpart of :meth:`debug_layout`. For
        every built widget it renders the same JSON-compatible fields at the
        widget's own top-left corner, so you can see geometry, requested size,
        and pack/grid details right where the widget sits instead of reading a
        printout. The badges are ``place``-managed labels over the root, so
        they never disturb the pack/grid layout, and they re-place themselves
        on resize (debounced).

        Toggle off with ``show_debug_layout(False)``.
        """
        root = self._root
        if root is None:
            return
        self._hide_debug_layout_badges()
        self._unbind_debug_layout_resize()
        if not on:
            if self._debug_padding_rebind is None:
                self._cancel_debug_overlay_poll()
            return
        self._build_debug_layout_badges()
        self._bind_debug_layout_resize()
        self._ensure_debug_overlay_poll()

    def _debug_layout_badge_lines(self, info: dict[str, Any]) -> str:
        """Render a widget's ``debug_layout()`` info as a short one-line badge."""
        parts: list[str] = []
        if info.get("name"):
            parts.append(info["name"])
        if info.get("class"):
            parts.append(info["class"])
        geom = info.get("geometry")
        if geom:
            parts.append(geom)
        parts.append(f"req {info.get('reqwidth')}x{info.get('reqheight')}")
        mgr = info.get("manager")
        if mgr:
            if mgr == "pack":
                pi = info.get("pack_info") or {}
                parts.append(
                    f"{pi.get('side')} {pi.get('fill')}"
                    f" expand{pi.get('expand')}"
                    f" padx{pi.get('padx')} pady{pi.get('pady')}"
                )
            elif mgr == "grid":
                gi = info.get("grid_info") or {}
                parts.append(
                    f"r{gi.get('row')} c{gi.get('column')}"
                    f" padx{gi.get('padx')} pady{gi.get('pady')}"
                )
        return " ".join(str(p) for p in parts)

    def _build_debug_layout_badges(self) -> None:
        """(Re)build the debug-layout badges from the current widget state."""
        root = self._root
        if root is None:
            return
        self._hide_debug_layout_badges()
        debug = self.layout_info()
        seen_rows: set[tuple[int, int]] = set()

        def _place(badge: tk.Label, x: int, y: int) -> None:
            while (x, y) in seen_rows:
                y += 18
            seen_rows.add((x, y))
            badge.place(x=x, y=y)

        for sec in debug.get("sections", []):
            for info in sec.get("widgets", []):
                name = info.get("name")
                if name in self._hidden_widgets:
                    # Do not badge a hidden (pack_forget/grid_remove) widget.
                    continue
                w = self._tk_widgets.get(name)
                if w is None or not bool(w.winfo_exists()):
                    continue
                # Skip widgets not currently mapped (e.g. inactive multiview
                # tabs / hidden stages) so no stray badge appears over them.
                # Only apply when the root is mapped (headless tests use a
                # withdrawn root, where every widget reports unmapped).
                try:
                    if root.winfo_ismapped() and not bool(w.winfo_ismapped()):
                        continue
                except tk.TclError:
                    pass
                badge = tk.Label(
                    root,
                    text=self._debug_layout_badge_lines(info),
                    bg="#e0e0e0",
                    fg="#000000",
                    relief="solid",
                    borderwidth=1,
                    font=t.font("small"),
                )
                # Clicking a badge lifts it to the front (topmost z-order).
                badge.bind("<Button-1>", lambda _e: badge.lift())
                try:
                    wx = w.winfo_rootx()
                    wy = w.winfo_rooty()
                    rrx = root.winfo_rootx()
                    rry = root.winfo_rooty()
                    _place(badge, wx - rrx, wy - rry)
                except tk.TclError:
                    pass
                self._debug_layout_badges.append(badge)

    def _hide_debug_layout_badges(self) -> None:
        """Destroy any previously created debug-layout badges."""
        for b in self._debug_layout_badges:
            try:
                b.destroy()
            except tk.TclError:
                pass
        self._debug_layout_badges.clear()

    def _bind_debug_layout_resize(self) -> None:
        """Re-place debug-layout badges on window resize (debounced)."""
        root = self._root
        if root is None or self._debug_layout_rebind is not None:
            return
        last = {"w": root.winfo_width(), "h": root.winfo_height()}
        pending: dict[str, str | None] = {"job": None}

        def _rerender(_event=None) -> None:
            w = root.winfo_width()
            h = root.winfo_height()
            if w == last["w"] and h == last["h"]:
                return
            last["w"], last["h"] = w, h
            if pending["job"] is not None:
                try:
                    root.after_cancel(pending["job"])
                except tk.TclError:
                    pass
            pending["job"] = root.after(60, self._build_debug_layout_badges)

        self._debug_layout_rebind = root.bind("<Configure>", _rerender, add="+")

    def _unbind_debug_layout_resize(self) -> None:
        """Remove the debug-layout resize re-render binding (if any)."""
        root = self._root
        if root is None or self._debug_layout_rebind is None:
            return
        try:
            root.unbind("<Configure>", self._debug_layout_rebind)
        except tk.TclError:
            pass
        self._debug_layout_rebind = None

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
        # Notify paired gutters so they re-sync their line numbers.
        for hook in self._text_set_hooks.get(name, []):
            try:
                hook()
            except tk.TclError:
                pass

    def on_text_set(self, name: str, hook: Callable[[], None]) -> None:
        """Register a callback to run after a text widget's content is replaced.

        Used by layout features (e.g. paired line-number gutters) that must
        stay in sync with a text widget's content. ``hook`` receives no args.
        """
        self._text_set_hooks.setdefault(name, []).append(hook)

    def text_tag_add(self, name: str, tag: str, start: str, end: str) -> None:
        """Apply a tag to a text range, even when read-only."""
        inner = self._text_inner.get(name)
        if inner is None:
            return
        inner.tag_add(tag, start, end)

    @property
    def root(self) -> tk.Tk | None:
        """Return the root Tk window (available after run or build_widgets).

        This serves as an escape hatch to access window-level Tk APIs directly
        (e.g. ``root.title()``, ``root.geometry()``, ``root.protocol()``,
        ``root.wm_*``, or custom Tcl commands).
        """
        return self._root

    @property
    def tcl(self) -> Any:
        """Return the underlying Tcl interpreter (``root.tk``), or ``None``."""
        return self._root.tk if self._root is not None else None

    def eval(self, script: str) -> Any:
        """Evaluate a raw Tcl script in the underlying Tcl interpreter.

        This serves as a first-class escape hatch to run arbitrary Tcl code,
        load packages, invoke Tcl macros, or perform high-performance bulk
        operations.
        """
        if self._root is None:
            raise RuntimeError("Cannot eval Tcl script before app is built or run.")
        return self._root.tk.eval(script)

    def call(self, *args: Any) -> Any:
        """Invoke a Tcl command directly with arguments via ``root.tk.call()``."""
        if self._root is None:
            raise RuntimeError("Cannot call Tcl command before app is built or run.")
        return self._root.tk.call(*args)

    @property
    def theme_tokens(self) -> t.ThemeTokens:
        """Return the active ThemeTokens instance for this application."""
        return self._theme_tokens

    def load_theme_tcl(
        self,
        script_or_path: str,
        theme_name: str | None = None,
    ) -> None:
        """Load and evaluate a Tcl theme definition script or file.

        *script_or_path* can be either a path to a ``.tcl`` theme file or a raw
        Tcl script string. If *theme_name* is provided, it is automatically
        activated via ``ttk.Style().theme_use(theme_name)``.

        Can be called before or after the app starts running.
        """
        if self._root is not None:
            content: str
            if os.path.isfile(script_or_path):
                with open(script_or_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = script_or_path
            self.eval(content)
            if theme_name:
                style = ttk.Style(self._root)
                style.theme_use(theme_name)
                self._theme = theme_name
        else:
            self._deferred_tcl_scripts.append((script_or_path, theme_name))

    def container(self, name: str) -> tk.Frame:
        """Return an unmanaged tk.Frame container created via Layout.container().

        This provides an explicit escape hatch for embedding custom raw tkinter
        widgets, Matplotlib canvas instances, or third-party GUI components.
        """
        w = self.get_widget(name)
        if not isinstance(w, tk.Frame):
            raise TypeError(
                f"Widget '{name}' is not a tk.Frame container (got {type(w).__name__})"
            )
        return w

    @contextlib.contextmanager
    def untracked(self) -> Generator[None, None, None]:
        """Temporarily suppress reactive state traces and updates within this block.

        Useful when executing high-throughput batch operations, streaming raw data
        into text/canvas widgets, or running bulk Tcl scripts without triggering
        reactive state passes.
        """
        prev = self._ingest_trace
        self._ingest_trace = False
        try:
            yield
        finally:
            self._ingest_trace = prev

    def widget_kind(self, name: str) -> str | None:
        for w in self._widgets:
            if w.name == name:
                return w.kind
        return None

    def widget_specs(self, *, kind: str | None = None) -> list[WidgetSpec]:
        if kind is None:
            return list(self._widgets)
        return [w for w in self._widgets if w.kind == kind]

    def layout_frame(self, name: str) -> tk.Misc | None:
        """Return the layout frame that owns the named widget.

        This is the parent frame a ``Layout`` section assigned to the widget
        (the same frame returned by ``app._widget_masters``). Use it to place
        widgets with grid/pack manually inside a section, or to re-parent a
        widget when switching layouts at runtime.

        Returns ``None`` when the widget has not been built yet.
        """
        return self._widget_masters.get(name)


    def debug_layout(self) -> dict[str, Any]:
        """Collect runtime geometry/state for every registered widget.

        Useful for diagnosing clipping, minsize, and geometry-manager issues
        without needing to sprinkle ``winfo_*`` calls in user code.  Output is
        JSON-compatible so it can be logged or handed to an agent.

        Safe to call after ``run()`` has returned: once the window is closed the
        Tk interpreter (and every widget) is destroyed, so ``winfo_*`` queries
        would otherwise raise ``TclError``.  ``debug_layout()`` reports
        ``"alive"`` as ``False`` and skips destroyed widgets instead of crashing.

        .. deprecated:: 0.4.11
            Use :meth:`layout_info` instead. ``debug_layout`` is a deprecated
            alias and will be removed in 0.5.x.
        """
        def _is_alive() -> bool:
            if self._root is None:
                return False
            try:
                return bool(self._root.winfo_exists())
            except tk.TclError:
                # The whole Tk interpreter is gone (e.g. root destroyed after
                # run()/mainloop exits); nothing can be queried anymore.
                return False

        alive = _is_alive()
        out: dict[str, Any] = {
            "title": self._title,
            "alive": alive,
            "sections": [],
        }
        if not alive:
            out["conflicts"] = []
            return out

        seen_sections: dict[int, dict[str, Any]] = {}
        for spec in self._widgets:
            name = spec.name
            w = self._tk_widgets.get(name)
            if w is None or not bool(w.winfo_exists()):
                continue
            master = w.master
            sec_id = id(master)
            if sec_id not in seen_sections:
                if master is None or not bool(master.winfo_exists()):
                    seen_sections[sec_id] = {
                        "master": master,
                        "master_class": None,
                        "master_geometry": None,
                        "destroyed": True,
                        "widgets": [],
                    }
                else:
                    seen_sections[sec_id] = {
                        "master": master,
                        "master_class": master.winfo_class(),
                        "master_geometry": master.winfo_geometry(),
                        "destroyed": False,
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
                        "padx": pi.get("padx"),
                        "pady": pi.get("pady"),
                    }
                elif mgr == "grid":
                    gi = w.grid_info()
                    info["grid_info"] = {
                        "row": gi.get("row"),
                        "column": gi.get("column"),
                        "sticky": gi.get("sticky"),
                        "padx": gi.get("padx"),
                        "pady": gi.get("pady"),
                    }
            except tk.TclError:
                pass
            seen_sections[sec_id]["widgets"].append(info)
        out["sections"] = list(seen_sections.values())

        # Detect geometry-manager conflicts. Tk forbids mixing pack/grid/place
        # on the same master; a registered widget's master may also host
        # manual widgets (e.g. an overlay placed with ``place``), which only
        # surface by inspecting the live child tree via ``winfo_manager``.
        conflicts: list[dict[str, Any]] = []
        for sec in out["sections"]:
            master = sec.get("master")
            managers: set[str] = set()
            widget_names: list[str] = []
            for w in sec["widgets"]:
                if w["manager"]:
                    managers.add(w["manager"])
                widget_names.append(w["name"])
            if master is not None and bool(master.winfo_exists()):
                try:
                    for child in master.winfo_children():
                        mgr = child.winfo_manager()
                        if mgr:
                            managers.add(mgr)
                        label = child.cget("text") if child.winfo_class() in (
                            "Label", "TLabel"
                        ) else child.winfo_class()
                        widget_names.append(label or child.winfo_name())
                except tk.TclError:
                    pass
            if len(managers) > 1:
                conflicts.append({
                    "master_class": sec["master_class"],
                    "managers": sorted(managers),
                    "widgets": widget_names,
                })
            sec.pop("master", None)
        out["conflicts"] = conflicts
        return out

    def layout_info(self) -> dict[str, Any]:
        """Collect runtime geometry/state for every registered widget.

        This is the non-debug-named counterpart of :meth:`debug_layout`: it
        returns the same JSON-compatible snapshot of each widget's geometry,
        requested size, and pack/grid details. ``debug_layout`` is a deprecated
        alias for this method (removed in 0.5.x); prefer ``layout_info``.

        Safe to call after ``run()`` has returned: once the window is closed the
        Tk interpreter (and every widget) is destroyed, so ``winfo_*`` queries
        would otherwise raise ``TclError``. It reports ``"alive"`` as ``False``
        and skips destroyed widgets instead of crashing.
        """
        return self.debug_layout()

    def check_layout_conflicts(self) -> list[dict[str, Any]]:
        """Return a list of geometry-manager conflicts, warning on each.

        Tcl/Tk raises ``TclError: conflicting geometry managers`` at runtime
        when a widget is managed by a different manager than its siblings on
        the same master. This helper surfaces the same condition without
        waiting for a failure: it inspects the live widget tree and reports
        any master whose children are split across multiple managers
        (``pack``/``grid``/``place``).

        Each returned item describes one conflicting master::

            {
                "master_class": "Frame",
                "managers": ["grid", "pack"],
                "widgets": ["left_pane", "location"],
            }

        A ``warnings.warn`` is emitted for every conflict found, so it can be
        used as a debugging aid after ``build_widgets`` (or inside ``run``).

        Safe to call after ``run()`` has returned: when the Tk interpreter has
        been torn down (the window was closed), ``debug_layout()`` reports no
        live widgets and this returns an empty list instead of raising.
        """
        debug = self.layout_info()
        conflicts: list[dict[str, Any]] = []
        for conflict in debug.get("conflicts", []):
            conflicts.append(conflict)
            warnings.warn(
                "Conflicting geometry managers on same master: "
                f"{conflict['managers']} for widgets "
                f"{conflict['widgets']} ({conflict['master_class']}). "
                "Pack/grid/place cannot be mixed on one widget.",
                stacklevel=2,
            )
        return conflicts

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
        on_resize: Callable[[int, int], None] | None = None,
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
            on_resize=on_resize,
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
        on_resize: Callable[[int, int], None] | None = None,
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
            on_resize=on_resize,
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
        on_resize: Callable[[int, int], None] | None = None,
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
            on_resize=on_resize,
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
        on_resize: Callable[[int, int], None] | None = None,
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
            chrome = tk.Frame(body, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
            chrome.pack(fill="x", pady=(0, t.SPACE[3]))
            self._multiview_header_container = chrome
            from nextpytk.theme import window_header
            self._multiview_header_fn = window_header
        else:
            chrome = None
            self._multiview_header_container = None
            self._multiview_header_fn = None

        if status_widgets:
            status_bar_frame = tk.Frame(body, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
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
            frame.configure(bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
            frames[view] = frame
            if view in layouts:
                layout = layouts[view]
                allowed = set(self.view_widget_names(view))
                row_jobs, grid_jobs = layout.mount_frames_into(
                    self, frame, allowed_widgets=allowed)
                jobs_by_view[view] = (layout, row_jobs, grid_jobs)
            else:
                # Same inner content margin as layout-managed views.
                inner = tk.Frame(frame, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
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
                self.pack_view_widgets(view, center_kinds=centered, fill="x", pady=t.SPACE[1])

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
        if self._debug_padding:
            self.show_debug_padding(True)
        self._install_resize_hook(on_resize)
        return root

    # ── state store properties ──

    @property
    def _state(self) -> dict[str, Any]:
        return self._store.state

    @_state.setter
    def _state(self, val: dict[str, Any]) -> None:
        self._store.state = val

    @property
    def _tk_vars(self) -> dict[str, tk.Variable]:
        return self._store.tk_vars

    @property
    def _syncing_var_keys(self) -> set[str]:
        return self._store.syncing_var_keys

    @property
    def _pending_ingest(self) -> set[str]:
        return self._store.pending_ingest

    @_pending_ingest.setter
    def _pending_ingest(self, val: set[str]) -> None:
        self._store.pending_ingest = val

    @property
    def _ingest_flush_job(self) -> str | None:
        return self._store.ingest_flush_job

    @_ingest_flush_job.setter
    def _ingest_flush_job(self, val: str | None) -> None:
        self._store.ingest_flush_job = val

    @property
    def _ingest_trace(self) -> bool:
        return self._store.ingest_trace

    @_ingest_trace.setter
    def _ingest_trace(self, val: bool) -> None:
        self._store.ingest_trace = val

    @property
    def _building(self) -> bool:
        return self._store.building

    @_building.setter
    def _building(self, val: bool) -> None:
        self._store.building = val

    # ── async job registration ──

    @property
    def _jobs(self) -> dict[str, AsyncJob]:
        return self._async_engine.jobs

    @property
    def _background_tasks(self) -> set[asyncio.Task[Any]]:
        return self._async_engine.background_tasks

    @property
    def _event_loop(self) -> asyncio.AbstractEventLoop | None:
        return self._async_engine.event_loop

    @_event_loop.setter
    def _event_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        self._async_engine.event_loop = loop

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
            return self._async_engine.register_job(name, fn)
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
        on_resize: Callable[[int, int], None] | None = None,
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
            chrome = tk.Frame(body, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
            chrome.pack(fill="x", pady=(0, t.SPACE[3]))
            self._multiview_header_container = chrome
        else:
            chrome = None
            self._multiview_header_container = None
        self._multiview_header_fn = None

        if status_widgets:
            status_bar_frame = tk.Frame(body, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
            status_bar_frame.pack(side="bottom", fill="x", pady=(t.SPACE[3], 0), padx=t.SPACE[6])
            self._multiview_status_container = status_bar_frame
        else:
            status_bar_frame = None
            self._multiview_status_container = None

        for name in header_widgets:
            self.set_widget_master(name, chrome if chrome is not None else body)
        for name in status_widgets:
            self.set_widget_master(name, status_bar_frame if status_bar_frame is not None else body)

        stage_container = tk.Frame(body, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
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
            frame = tk.Frame(stage_container, name=f"stageframe_{stage}", bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
            self._stage_frames[stage] = frame
            if stage in layouts:
                layout = layouts[stage]
                allowed = set(self.view_widget_names(stage))
                row_jobs, grid_jobs = layout.mount_frames_into(self, frame, allowed_widgets=allowed)
                jobs_by_stage[stage] = (layout, row_jobs, grid_jobs)
            else:
                inner = tk.Frame(frame, bg=self._theme_tokens.bg, bd=0, highlightthickness=0)
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
                self.pack_view_widgets(stage, center_kinds=centered, fill="x", pady=t.SPACE[1])

        active = str(self._state.get(key, stages[0] if stages else ""))
        if active not in stages:
            active = stages[0] if stages else ""
        self._render_stage(active, key=key, centered=centered)

        if on_ready is not None:
            on_ready(self)

        self.draw_canvas_items()
        self.sync()
        self._set_initial_focus()
        if self._debug_padding:
            self.show_debug_padding(True)
        self._install_resize_hook(on_resize)
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

    def spawn(self, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        """Schedule an async task on the running event loop.

        Raises RuntimeError if no event loop is running.
        """
        return self._async_engine.spawn(coro)

    async def _async_poll(self) -> None:
        """Poll Tk events cooperatively with asyncio."""
        await self._async_engine.async_poll(self._root)

    def stop(self) -> None:
        """Signal the async mainloop to stop gracefully."""
        self._async_engine.stop()

    async def _async_mainloop(self) -> None:
        """Cooperative async mainloop: Tk event processing + asyncio scheduler."""
        await self._async_engine.async_mainloop(self._root)

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

    # ── state management ──

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
        if spec.kind == "filepicker":
            self._invoke_filepicker(spec)
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
        # Mark the keys being written by the framework so their write traces
        # (if ingest_trace is on) do not loop the value back into state.
        self._syncing_var_keys.update(update_to_apply)
        try:
            for key, val in update_to_apply.items():
                spec = self._spec(key)
                if spec is not None and not spec.sync:
                    continue
                var = self._tk_vars.get(key)
                if var is None:
                    continue
                s = "" if val is None else str(val)
                var.set(s)
                w = self._tk_widgets.get(key)
                if isinstance(w, (tk.Entry, ttk.Entry)):
                    self._apply_entry_value_after_state(key, w, var, s)
        finally:
            self._syncing_var_keys.difference_update(update_to_apply)
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

    def _register_var(self, key: str, var: tk.Variable) -> None:
        """Register a Tcl variable under *key*, installing an ingest trace."""
        self._store.register_var(key, var, on_ingest=self._on_var_ingest)

    def _on_var_ingest(self, key: str) -> None:
        """Trace callback: a user edit changed ``var``; queue it for ingest."""
        self._store.on_var_ingest(key, self._root, self._flush_ingest)

    def _flush_ingest(self) -> None:
        """Flush queued user edits into ``state`` in one batched pass."""
        self._ingest_flush_job = None
        if not self._pending_ingest:
            return
        pending = self._pending_ingest
        self._pending_ingest = set()
        update: dict[str, Any] = {}
        for key in pending:
            var = self._tk_vars.get(key)
            if var is None:
                continue
            try:
                update[key] = var.get()
            except tk.TclError:
                continue
        if update:
            self._apply_state_dict(update, full=False)

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
                items_key = spec.extras.get("items_key")
                if items_key is not None:
                    keys.add(str(items_key))
                keys.add(spec.name)
            elif spec.kind == "progressbar":
                keys.add(str(spec.extras.get("state_key", spec.name)))
                keys.add(f"{spec.name}_running")
                keys.add(f"{spec.name}_mode")
            elif spec.kind == "combobox":
                values_key = spec.extras.get("values_key")
                if values_key is not None:
                    keys.add(str(values_key))
                keys.add(str(spec.extras.get("state_key", spec.name)))
            elif spec.kind in ("label", "status", "message", "entry", "text",
                               "button", "bind"):
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
        if getattr(w, "_nextpytk_ph_native", False):
            # Native placeholder never writes into the variable.
            return var.get()
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
            if getattr(w, "_nextpytk_ph_native", False):
                return
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
            if getattr(w, "_nextpytk_ph_native", False):
                return
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
        if getattr(w, "_nextpytk_ph_native", False):
            # Native placeholder is independent of the variable; nothing to do.
            return
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

    def _sync_widgets(self) -> None:
        """Push state to label, button, text, and listbox widgets."""
        for spec in self._widgets:
            if not spec.sync:
                continue
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
                target = str(value)
                if str(tk_w.cget("text")) != target:
                    tk_w.configure(text=target)  # type: ignore[call-arg]
            elif spec.kind == "button":
                # Buttons keep their declared label unless a state value is
                # explicitly set (e.g. a callback returned {"<name>": text}).
                if spec.name not in self._state:
                    continue
                tk_w = self._tk_widgets.get(spec.name)
                if tk_w is None:
                    continue
                target = str(self._state[spec.name])
                if str(tk_w.cget("text")) != target:
                    tk_w.configure(text=target)  # type: ignore[call-arg]
            elif spec.kind == "text":
                self._sync_text_widget(spec)
            elif spec.kind == "listbox" and spec.extras.get("items_key") is not None:
                self._sync_listbox_items(spec)
            elif spec.kind == "combobox" and spec.extras.get("values_key") is not None:
                self._sync_combobox_values(spec)

    def _sync_text_widget(self, spec: WidgetSpec) -> None:
        """Update a text widget from state if the content changed."""
        if not spec.sync or spec.name not in self._state:
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
            if spec.kind != "treeview" or not spec.sync:
                continue
            rows_key = spec.extras.get("rows_key", f"{spec.name}_rows")
            if rows_key in update:
                return True
        return False

    def _treeview_update_touches_selection(self, update: dict[str, Any]) -> bool:
        """True when *update* carries a treeview selection index (not row data)."""
        for spec in self._widgets:
            if spec.kind == "treeview" and spec.sync and spec.name in update:
                return True
        return False

    def _sync_widgets_for_keys(self, update: dict[str, Any]) -> None:
        """Update only label/status/message/button/text widgets named in *update*."""
        for spec in self._widgets:
            if not spec.sync:
                continue
            if spec.kind in ("label", "status", "message", "button"):
                if spec.name not in update:
                    continue
                tk_w = self._tk_widgets.get(spec.name)
                if tk_w is None:
                    continue
                target = str(update[spec.name])
                if str(tk_w.cget("text")) != target:
                    tk_w.configure(text=target)  # type: ignore[call-arg]
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
            items_key = spec.extras.get("items_key")
            if items_key is None:
                continue
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
            items_key = spec.extras.get("items_key")
            if items_key is None:
                continue
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
            values_key = spec.extras.get("values_key")
            if values_key is None:
                continue
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
            values_key = spec.extras.get("values_key")
            if values_key is None:
                continue
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
            "filepicker": self._build_filepicker,
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

        self._building = True
        try:
            self._build_widgets_inner()
        finally:
            self._building = False

    def _build_widgets_inner(self) -> None:
        """Create tkinter widgets from registered specs (inside build guard)."""
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
            self._apply_widget_overrides(spec)
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

    def _relax_minsize(
        self,
        *,
        explicit_geometry: str | None = None,
        default_min: tuple[int, int] = (380, 260),
    ) -> None:
        """Lower the window minimum size when the content requests less.

        ``configure_window`` applies a default ``minsize`` (380x260) so small
        dialogs are still comfortably usable and accessible. But for a tiny
        app — e.g. a single-button hello demo whose requested size is
        ``146x123`` — that default forcibly stretches the window, wasting
        vertical space.

        This helper re-measures the layout's requested size after widgets are
        built (``update_idletasks``) and clamps the minimum to
        ``min(default, requested)`` per axis. The minimum is only ever
        *lowered*, never raised, so it remains a lower bound: a window whose
        content requests more than the default still grows to fit
        (``minsize`` only sets a floor, it does not cap the size).

        When the caller passes an explicit ``geometry`` (e.g.
        ``"720x480"``) the window size is intentional, so the minimum is left
        untouched.
        """
        root = self._root
        if root is None or explicit_geometry:
            return

        def _apply() -> None:
            try:
                root.update_idletasks()
                req_w, req_h = root.winfo_reqwidth(), root.winfo_reqheight()
                min_w, min_h = root.wm_minsize()
                if min_w <= 0 and min_h <= 0:
                    return
                new_w = max(1, min(req_w, min_w))
                new_h = max(1, min(req_h, min_h))
                if (new_w, new_h) != (min_w, min_h):
                    # minsize is a floor, not a cap: lowering it does not
                    # shrink a window already mapped at the larger default.
                    root.minsize(new_w, new_h)
                    # Deferring to after_idle lets the first map settle; then
                    # reset the explicit geometry so the window shrinks to its
                    # requested size. Using geometry("") (rather than pinning
                    # to a fixed "WxH") keeps the window flexible: if content
                    # later grows (e.g. a button label widens), the window
                    # follows its natural requested size instead of clipping.
                    root.after_idle(lambda: root.geometry(""))
            except tk.TclError:
                pass

        try:
            root.after_idle(_apply)
        except tk.TclError:
            pass

    def _install_resize_hook(
        self,
        on_resize: Callable[[int, int], None] | None,
    ) -> None:
        """Install a debounced, size-change-only ``<Configure>`` handler.

        This is the framework-managed counterpart to hand-rolled
        ``root.bind("<Configure>", ...)`` in user code. It exists so app
        developers do not have to reason about Tk's ``<Configure>`` semantics
        (which fire for *every* child widget, not just the toplevel) or about
        the infinite-loop risk of reconfiguring widgets from inside the
        handler.

        Guarantees:

        - **Toplevel only**: child-widget ``<Configure>`` events are ignored
          (``event.widget != root``), so reconfiguring a child from the
          callback cannot re-trigger the handler.
        - **Size-change only**: the callback fires only when the window's
          ``(width, height)`` actually changed, so a callback that calls
          ``configure``/``pack_configure`` (which can emit ``<Configure>``
          without changing the toplevel size) does not loop.
        - **Debounced**: rapid resize storms are coalesced into a single
          callback via ``after``, so the callback runs at most once per
          settle window.

        The callback is invoked as ``on_resize(width, height)``.
        """
        root = self._root
        if root is None or on_resize is None:
            return

        last = {"w": root.winfo_width(), "h": root.winfo_height()}
        pending: dict[str, str | None] = {"job": None}

        def _on_configure(event: tk.Event[tk.Misc] | None = None) -> None:
            # Tk fires <Configure> for every child widget too; only react to
            # the toplevel itself.
            if event is not None and event.widget != root:
                return
            w = root.winfo_width()
            h = root.winfo_height()
            if (w, h) == (last["w"], last["h"]):
                return
            last["w"], last["h"] = w, h
            # Debounce: coalesce a burst of <Configure> events into one call.
            if pending["job"] is not None:
                try:
                    root.after_cancel(pending["job"])
                except tk.TclError:
                    pass
            pending["job"] = root.after(60, lambda: on_resize(w, h))

        root.bind("<Configure>", _on_configure, add="+")

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

            sb_a = self._text_scrollbars.get(name_a)
            sb_b = self._text_scrollbars.get(name_b)

            def _sync_from_a(
                *args: Any,
                source: tk.Text = text_a,
                target: tk.Text = text_b,
                sb: ttk.Scrollbar | None = sb_a,
            ) -> None:
                target.yview_moveto(source.yview()[0])
                if sb is not None:
                    sb.set(*args)

            def _sync_from_b(
                *args: Any,
                source: tk.Text = text_b,
                target: tk.Text = text_a,
                sb: ttk.Scrollbar | None = sb_b,
            ) -> None:
                target.yview_moveto(source.yview()[0])
                if sb is not None:
                    sb.set(*args)

            text_a.configure(yscrollcommand=_sync_from_a)
            text_b.configure(yscrollcommand=_sync_from_b)

    # ── a11y helpers (Tk 9.1+ / TIP 733) ──

    def _call_accessible(self, *args: str) -> bool:
        """Call ``tk accessible ...``, returning True on success."""
        return self._a11y.call_accessible(self._root, *args)

    def _apply_a11y(self, spec: WidgetSpec) -> None:
        """Route ``WidgetSpec.role`` / ``description`` to Tk accessible attrs."""
        self._a11y.apply_a11y(self._root, self._a11y_target(spec), spec)

    def _apply_a11y_to_layout_frames(self) -> None:
        """Mark intermediate layout frames as grouping containers."""
        frames = [f for f in self._widget_masters.values() if isinstance(f, (tk.Misc,))]
        self._a11y.apply_to_layout_frames(self._root, frames)

    def _emit_a11y_selection_change(self, spec: WidgetSpec) -> None:
        """Notify AT that the selection of *spec* has changed."""
        self._a11y.emit_selection_change(self._root, self._a11y_target(spec))

    def _emit_a11y_value_change(self, spec: WidgetSpec) -> None:
        """Notify AT that the value of *spec* has changed."""
        key = spec.extras.get("state_key", spec.name)
        value = str(self._state.get(key, ""))
        self._a11y.emit_value_change(self._root, self._a11y_target(spec), value)

    def _emit_a11y_state_change(self, spec: WidgetSpec) -> None:
        """Notify AT that the checked/selected state of *spec* has changed."""
        if spec.kind == "checkbutton":
            key = str(spec.extras.get("state_key", spec.name))
        elif spec.kind == "radiobutton":
            key = str(spec.extras.get("group_key", "radio"))
        else:
            key = spec.name
        value = str(self._state.get(key, ""))
        self._a11y.emit_state_change(self._root, self._a11y_target(spec), spec, value, key)

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

    def _auto_layout(self) -> Any:
        """Build a default single-column layout from registered widgets.

        Used when ``run()`` is called without ``layout=``. Widgets appear in
        registration order; chrome helpers (e.g. ``@app.status``) that already
        mounted themselves into the root are skipped so they are not placed
        twice. Returns ``None`` when there are no widgets to arrange.
        """
        from nextpytk.layout import Layout
        names = [
            w.name for w in self._widgets
            if w.name not in self._tk_widgets
        ]
        if not names:
            return None
        return Layout.from_list(names)

    def _layout_names(self, layout: Any) -> set[str]:
        """Collect the widget names referenced by a resolved Layout object."""
        try:
            names = layout.widget_names()
        except AttributeError:
            return set()
        return names

    def _warn_orphan_layout_names(self, layout: Any) -> None:
        """Warn about widget names in ``layout`` that are not registered.

        A name that appears in the layout but has no matching registered widget
        (or chrome-mounted widget) silently renders an empty section. Report it
        so the user notices the mismatch between ``app.run(layout=[...])`` and
        the ``@app.*`` registrations.
        """
        layout_names = self._layout_names(layout)
        if not layout_names:
            return
        registered = {w.name for w in self._widgets} | set(self._tk_widgets)
        for name in sorted(layout_names - registered):
            print(
                f"nextpytk: layout references {name!r}, but no widget with that "
                f"name is registered. The section will be empty. Did you forget "
                f"to decorate it (e.g. @app.button({name!r}))?",
                file=sys.stderr,
            )

    def run(
        self,
        *,
        layout: Any = None,
        initial_state: dict[str, Any] | None = None,
        multiview: str | None = None,
        stages: str | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        on_resize: Callable[[int, int], None] | None = None,
        geometry: str | None = None,
    ) -> None:
        """Build and run the Tk application.

        on_ready is called after widget building and state application,
        just before "mainloop()". Use it for dynamic widget population,
        key bindings, or other imperative setup that needs widgets to exist.
        on_resize is called with ``(width, height)`` whenever the window is
        resized. It is debounced and only fires when the size actually
        changes, so the callback can safely reconfigure widgets without
        causing an infinite ``<Configure>`` loop.
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
                on_resize=on_resize,
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
                on_resize=on_resize,
                tabposition=cfg.get("tabposition", "nw"),
            )
            return

        self._root = tk.Tk()
        self._root.title(self._title)
        if geometry:
            self._root.geometry(geometry)
        self._configure_theme(self._root)
        self.clear_runtime()

        if layout is None:
            # Sugar: with no layout, auto-arrange every registered widget into
            # a single vertical column in registration order. Ideal for quick
            # demos and beginner-friendly single-button apps.
            layout = self._auto_layout()
        if isinstance(layout, list):
            from nextpytk.layout import Layout
            layout = Layout.from_list(layout)
        self._warn_orphan_layout_names(layout)
        if layout is not None:
            layout.mount_frames(self)

        # Mount swap-target variant frames before widgets are built so each
        # variant's widgets land in their own section frame, not the root.
        self._build_swap_variants()

        self._build_widgets()

        if layout is not None:
            layout.pack_children(self)

        # Pack/grid each variant's section children now that widgets exist.
        self._pack_swap_variants()

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
        self._relax_minsize(explicit_geometry=geometry)
        if self._debug_padding:
            self.show_debug_padding(True)
        self._install_resize_hook(on_resize)
        self._root.mainloop()

    def run_async(
        self,
        *,
        layout: Any = None,
        initial_state: dict[str, Any] | None = None,
        multiview: str | None = None,
        stages: str | None = None,
        on_ready: Callable[[TkApp], None] | None = None,
        on_resize: Callable[[int, int], None] | None = None,
        geometry: str | None = None,
    ) -> None:
        """Build and run the Tk application with asyncio event loop.

        Use ``app.spawn(coro)`` inside ``on_ready`` to schedule async tasks.
        on_resize is called with ``(width, height)`` whenever the window is
        resized (debounced, size-change only).
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
                on_resize=on_resize,
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
                on_resize=on_resize,
                tabposition=cfg.get("tabposition", "nw"),
            ))
            return

        asyncio.run(self._async_run(layout, initial_state, on_ready, on_resize, geometry))

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
        on_resize: Callable[[int, int], None] | None = None,
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
            on_resize=on_resize,
        )
        await self._async_mainloop()

    async def _async_run(
        self,
        layout: Any | None,
        initial_state: dict[str, Any] | None,
        on_ready: Callable[[TkApp], None] | None,
        on_resize: Callable[[int, int], None] | None,
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

        if layout is None:
            layout = self._auto_layout()
        if isinstance(layout, list):
            from nextpytk.layout import Layout
            layout = Layout.from_list(layout)
        self._warn_orphan_layout_names(layout)
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
        self._relax_minsize(explicit_geometry=geometry)
        if self._debug_padding:
            self.show_debug_padding(True)
        self._install_resize_hook(on_resize)
        await self._async_mainloop()

    # ── schema export (for AI agents / LLM Function Calling) ──

    def schema(self) -> dict[str, Any]:
        """Export widget registry as JSON-compatible schema."""
        return SchemaExporter.export(
            title=self._title,
            widgets=self._widgets,
            state=self._state,
            combobox_values_fn=self._combobox_values,
            listbox_items_fn=self._listbox_items,
        )

    @property
    def state(self) -> dict[str, Any]:
        return dict(self._state)
