"""Fluent DSL types for Layout: tkinter constants exposed as typed class constants.

Each type (Side, Fill, Sticky, …) is a class with class-level constants
that double as Literal type annotations. Pyright/mypy validate both the
value and the type through the same name.

Usage::

    from nextpytk.types import Side, Fill
    Layout().section("msg", side=Side.LEFT, fill=Fill.X)
"""

from __future__ import annotations

import sys
import warnings
from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import Any, Literal, Required, TypedDict, Unpack


# ── pack side ──

class Side:
    """Pack ``side`` option. Use ``Side.LEFT`` / ``Side.RIGHT`` / ``Side.TOP`` / ``Side.BOTTOM``."""

    LEFT: Literal["left"] = "left"
    RIGHT: Literal["right"] = "right"
    TOP: Literal["top"] = "top"
    BOTTOM: Literal["bottom"] = "bottom"

SideLike = Literal["left", "right", "top", "bottom"]


# ── pack fill ──

class Fill:
    """Pack ``fill`` option. Use ``Fill.X`` / ``Fill.Y`` / ``Fill.BOTH`` / ``Fill.NONE``."""

    NONE: Literal["none"] = "none"
    X: Literal["x"] = "x"
    Y: Literal["y"] = "y"
    BOTH: Literal["both"] = "both"

FillLike = Literal["none", "x", "y", "both"]


# ── expand ──

ExpandLike = bool | Literal[0, 1]


# ── anchor ──

class Anchor:
    """Anchor option. Use ``Anchor.N`` / ``Anchor.CENTER`` etc."""

    N: Literal["n"] = "n"
    S: Literal["s"] = "s"
    E: Literal["e"] = "e"
    W: Literal["w"] = "w"
    NE: Literal["ne"] = "ne"
    NW: Literal["nw"] = "nw"
    SE: Literal["se"] = "se"
    SW: Literal["sw"] = "sw"
    CENTER: Literal["center"] = "center"

AnchorLike = Literal["n", "s", "e", "w", "ne", "nw", "se", "sw", "center"]


# ── sticky (grid) ──

class Sticky:
    """Grid ``sticky`` option. Use ``Sticky.NSEW`` / ``Sticky.EW`` etc.

    Compass directions (tkinter native):
        N (north/top), S (south/bottom), E (east/right), W (west/left)

    Convenience aliases for pack users:
        Sticky.TOP = Sticky.N, Sticky.BOTTOM = Sticky.S,
        Sticky.LEFT = Sticky.W, Sticky.RIGHT = Sticky.E
    """

    N: Literal["n"] = "n"
    S: Literal["s"] = "s"
    E: Literal["e"] = "e"
    W: Literal["w"] = "w"
    NSEW: Literal["nsew"] = "nsew"
    NS: Literal["ns"] = "ns"
    EW: Literal["ew"] = "ew"
    NONE: Literal[""] = ""

    # Convenience aliases (pack → grid translation)
    TOP: Literal["n"] = "n"
    BOTTOM: Literal["s"] = "s"
    LEFT: Literal["w"] = "w"
    RIGHT: Literal["e"] = "e"
    TOP_BOTTOM: Literal["ns"] = "ns"
    LEFT_RIGHT: Literal["ew"] = "ew"

StickyLike = Literal["n", "s", "e", "w", "nsew", "ns", "ew", ""]


# ── widget state ──

class State:
    """Widget ``state`` option: ``State.NORMAL`` / ``State.DISABLED`` / ``State.ACTIVE``."""

    NORMAL: Literal["normal"] = "normal"
    DISABLED: Literal["disabled"] = "disabled"
    ACTIVE: Literal["active"] = "active"

StateLike = Literal["normal", "disabled", "active"]


# ── orient ──

class Orient:
    """Scale ``orient`` option: ``Orient.HORIZONTAL`` / ``Orient.VERTICAL``."""

    HORIZONTAL: Literal["horizontal"] = "horizontal"
    VERTICAL: Literal["vertical"] = "vertical"

OrientLike = Literal["horizontal", "vertical"]


# ── relief ──

class Relief:
    """Border ``relief`` option."""

    FLAT: Literal["flat"] = "flat"
    RAISED: Literal["raised"] = "raised"
    SUNKEN: Literal["sunken"] = "sunken"
    GROOVE: Literal["groove"] = "groove"
    RIDGE: Literal["ridge"] = "ridge"
    SOLID: Literal["solid"] = "solid"

ReliefLike = Literal["flat", "raised", "sunken", "groove", "ridge", "solid"]


# ── justify ──

class Justify:
    """Text ``justify`` option."""

    LEFT: Literal["left"] = "left"
    RIGHT: Literal["right"] = "right"
    CENTER: Literal["center"] = "center"

JustifyLike = Literal["left", "right", "center"]


# ── wrap (text widgets) ──

class Wrap:
    """Text ``wrap`` option. ``Wrap.WORD`` (default), ``Wrap.NONE`` (logical
    lines + horizontal scroll), or ``Wrap.CHAR``.

    ``Wrap.NONE`` disables line wrapping so each line stays on a single
    (logical) row; the widget then exposes a horizontal scrollbar when the
    content is wider than the viewport.
    """

    WORD: Literal["word"] = "word"
    NONE: Literal["none"] = "none"
    CHAR: Literal["char"] = "char"

WrapLike = Literal["word", "none", "char"]


# ── selectmode ──

class SelectMode:
    """Listbox ``selectmode`` option."""

    SINGLE: Literal["single"] = "single"
    BROWSE: Literal["browse"] = "browse"
    MULTIPLE: Literal["multiple"] = "multiple"
    EXTENDED: Literal["extended"] = "extended"

SelectModeLike = Literal["single", "browse", "multiple", "extended"]


# ── takefocus (Tab key focus traversal) ──

class TakeFocus:
    """Widget ``takefocus`` option for Tab-order control.

    Use ``TakeFocus.YES`` / ``TakeFocus.NO`` / ``TakeFocus.DEFAULT``.
    ``DEFAULT`` (``\"\"``) lets Tk decide per widget class.

    Tab traversal is how keyboard-only users reach controls
    (WCAG 2.1.1 Keyboard, 2.4.3 Focus Order).
    """

    DEFAULT: Literal[""] = ""
    YES: Literal[1] = 1
    NO: Literal[0] = 0

TakeFocusLike = bool | Literal["", 0, 1]

# ── widget callbacks (re-exported from app.py to avoid circular imports) ──

ButtonCallback = Callable[[dict[str, Any]], dict[str, Any]]
ValueCallback = Callable[[str], dict[str, Any]]
ListboxSelectCallback = Callable[[int], dict[str, Any]]
BoolCallback = Callable[[bool], dict[str, Any]]
LabelCallback = Callable[[], str | dict[str, Any]]
BindCallback = Callable[[dict[str, Any]], dict[str, Any]]
TreeviewSelectCallback = Callable[[int, list[Any]], dict[str, Any]]
TreeviewActivateCallback = Callable[[int, list[Any]], dict[str, Any]]
FilepickerCallback = Callable[..., dict[str, Any]]

# ── generic event sequences (bindings, listbox events, etc.) ──

@lru_cache(maxsize=1)
def _primary_button_number() -> Literal[1, 3]:
    """Detect the OS primary mouse button and return its tkinter number.

    Returns ``1`` for the physically left button (default on right-handed
    setups) and ``3`` when the OS has swapped the primary button to the
    physically right button (left-handed setups).

    The detection is best-effort: Windows via ``GetSystemMetrics``,
    macOS via ``NSUserDefaults``, Linux/GNOME via ``gsettings``.
    If detection fails, ``1`` is returned as the safe default.

    The result is cached after the first call because mouse-button swap
    is a system preference that rarely changes during a process lifetime.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            SM_SWAPBUTTON = 23
            swapped = ctypes.windll.user32.GetSystemMetrics(SM_SWAPBUTTON)
            return 3 if swapped else 1
        except Exception:  # pragma: no cover - defensive
            return 1

    if sys.platform == "darwin":
        try:
            # pyright ignore: Foundation (PyObjC) is only available on macOS.
            from Foundation import NSUserDefaults  # type: ignore[import-not-found]

            defaults = NSUserDefaults.standardUserDefaults()
            swapped = defaults.boolForKey_("com.apple.mouse.swapLeftRightButton")
            return 3 if swapped else 1
        except Exception:  # pragma: no cover - defensive
            return 1

    # Linux / other Unix: try common GNOME/gsettings path
    try:
        import subprocess

        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.peripherals.mouse", "left-handed"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        swapped = result.stdout.strip() == "true"
        return 3 if swapped else 1
    except Exception:  # pragma: no cover - defensive
        return 1


def primary_click() -> str:
    """Return the event sequence for a single click on the OS primary button."""
    return f"<Button-{_primary_button_number()}>"


def primary_double_click() -> str:
    """Return the event sequence for a double-click on the OS primary button."""
    return f"<Double-Button-{_primary_button_number()}>"


def primary_button_release() -> str:
    """Return the event sequence for releasing the OS primary button."""
    return f"<ButtonRelease-{_primary_button_number()}>"


class _LazyEventSeq:
    """Descriptor: calls *fn* on every class-attribute access.

    Used so ``EventSeq.PRIMARY_DOUBLE_CLICK`` re-evaluates
    ``primary_double_click()`` each time rather than freezing the
    value at import time.
    """

    def __init__(self, fn: Callable[[], str]) -> None:
        self._fn = fn

    def __get__(self, obj: object | None, objtype: type | None = None) -> str:
        return self._fn()


class _DeprecatedEventSeq:
    """Descriptor that returns a fixed event string and warns once on access."""

    def __init__(self, value: str, *, message: str) -> None:
        self._value = value
        self._message = message
        self._warned = False

    def __get__(self, obj: object | None, objtype: type | None = None) -> str:
        if not self._warned:
            warnings.warn(self._message, DeprecationWarning, stacklevel=2)
            self._warned = True
        return self._value


class EventSeq:
    """Common tkinter event sequences used throughout nextpytk.

    In tkinter terminology, an **event sequence** is the string pattern passed
    to ``bind`` (e.g. ``"<Return>"`` or ``"<Double-Button-1>"``). ``Seq`` is
    shorthand for *sequence*, not a list or numbered series.

    Use these constants for IDE completion and typo protection with any
    binding API: ``@app.bind(sequence=EventSeq.RETURN)``,
    ``@app.listbox(..., events={EventSeq.RETURN: ...})``, etc.
    Arbitrary tkinter event strings are still accepted at runtime.

    Primary-button helpers (a11y-aware):
        ``EventSeq.PRIMARY_CLICK``, ``EventSeq.PRIMARY_DOUBLE_CLICK``, and
        ``EventSeq.PRIMARY_BUTTON_RELEASE`` return the tkinter event sequence
        for the OS-configured primary mouse button. On left-handed setups
        these resolve to Button-3 instead of Button-1. They are lazy
        descriptors and are the recommended choice for widget-level mouse
        bindings.

    Deprecated:
        ``EventSeq.DOUBLE_CLICK`` is a deprecated alias of
        ``EventSeq.DOUBLE_BUTTON_1`` and will be removed in v0.5.0.
        Use ``EventSeq.PRIMARY_DOUBLE_CLICK`` or ``DOUBLE_BUTTON_1`` instead.
    """

    # ── keyboard ──
    RETURN: Literal["<Return>"] = "<Return>"
    ESCAPE: Literal["<Escape>"] = "<Escape>"
    TAB: Literal["<Tab>"] = "<Tab>"
    BACKSPACE: Literal["<BackSpace>"] = "<BackSpace>"
    DELETE: Literal["<Delete>"] = "<Delete>"
    INSERT: Literal["<Insert>"] = "<Insert>"
    HOME: Literal["<Home>"] = "<Home>"
    END: Literal["<End>"] = "<End>"
    PAGE_UP: Literal["<Prior>"] = "<Prior>"
    PAGE_DOWN: Literal["<Next>"] = "<Next>"

    # ── arrow / function keys ──
    UP: Literal["<Up>"] = "<Up>"
    DOWN: Literal["<Down>"] = "<Down>"
    LEFT: Literal["<Left>"] = "<Left>"
    RIGHT: Literal["<Right>"] = "<Right>"
    F1: Literal["<F1>"] = "<F1>"
    F2: Literal["<F2>"] = "<F2>"
    F3: Literal["<F3>"] = "<F3>"
    F4: Literal["<F4>"] = "<F4>"
    F5: Literal["<F5>"] = "<F5>"
    F6: Literal["<F6>"] = "<F6>"
    F7: Literal["<F7>"] = "<F7>"
    F8: Literal["<F8>"] = "<F8>"
    F9: Literal["<F9>"] = "<F9>"
    F10: Literal["<F10>"] = "<F10>"
    F11: Literal["<F11>"] = "<F11>"
    F12: Literal["<F12>"] = "<F12>"

    # ── mouse ──
    BUTTON_1: Literal["<Button-1>"] = "<Button-1>"
    BUTTON_2: Literal["<Button-2>"] = "<Button-2>"
    BUTTON_3: Literal["<Button-3>"] = "<Button-3>"
    BUTTON_RELEASE_1: Literal["<ButtonRelease-1>"] = "<ButtonRelease-1>"
    DOUBLE_BUTTON_1: Literal["<Double-Button-1>"] = "<Double-Button-1>"
    DOUBLE_BUTTON_2: Literal["<Double-Button-2>"] = "<Double-Button-2>"
    DOUBLE_BUTTON_3: Literal["<Double-Button-3>"] = "<Double-Button-3>"
    DOUBLE_CLICK = _DeprecatedEventSeq(  # type: ignore[misc]
        "<Double-Button-1>",
        message=(
            "EventSeq.DOUBLE_CLICK is deprecated; use "
            "EventSeq.PRIMARY_DOUBLE_CLICK or EventSeq.DOUBLE_BUTTON_1. "
            "Will be removed in v0.5.0."
        ),
    )
    MOTION: Literal["<Motion>"] = "<Motion>"
    MOUSE_WHEEL: Literal["<MouseWheel>"] = "<MouseWheel>"
    ENTER: Literal["<Enter>"] = "<Enter>"
    LEAVE: Literal["<Leave>"] = "<Leave>"

    # ── focus / window ──
    FOCUS_IN: Literal["<FocusIn>"] = "<FocusIn>"
    FOCUS_OUT: Literal["<FocusOut>"] = "<FocusOut>"
    CONFIGURE: Literal["<Configure>"] = "<Configure>"
    MAP: Literal["<Map>"] = "<Map>"
    UNMAP: Literal["<Unmap>"] = "<Unmap>"
    DESTROY: Literal["<Destroy>"] = "<Destroy>"
    VISIBILITY: Literal["<Visibility>"] = "<Visibility>"

    # ── virtual events ──
    LISTBOX_SELECT: Literal["<<ListboxSelect>>"] = "<<ListboxSelect>>"
    COMBOBOX_SELECTED: Literal["<<ComboboxSelected>>"] = "<<ComboboxSelected>>"
    TREEVIEW_SELECT: Literal["<<TreeviewSelect>>"] = "<<TreeviewSelect>>"
    TREEVIEW_OPEN: Literal["<<TreeviewOpen>>"] = "<<TreeviewOpen>>"
    TREEVIEW_CLOSE: Literal["<<TreeviewClose>>"] = "<<TreeviewClose>>"
    NOTEBOOK_TAB_CHANGED: Literal["<<NotebookTabChanged>>"] = "<<NotebookTabChanged>>"

    # ── a11y-aware primary button (lazy descriptors) ──
    PRIMARY_CLICK: _LazyEventSeq = _LazyEventSeq(primary_click)
    PRIMARY_DOUBLE_CLICK: _LazyEventSeq = _LazyEventSeq(primary_double_click)
    PRIMARY_BUTTON_RELEASE: _LazyEventSeq = _LazyEventSeq(primary_button_release)


# Tkinter accepts arbitrary event-pattern strings (modifier combinations,
# custom virtual events, platform-specific events, etc.), so the type alias
# intentionally stays as ``str``. Use EventSeq constants for IDE completion.
EventSeqLike = str


class _ListboxEventMeta(type):
    """Warn once when any public ``ListboxEvent`` attribute is accessed."""

    _warned: bool = False

    def __getattribute__(cls, name: str) -> Any:
        if name.startswith("_") or name in ("mro",):
            return type.__getattribute__(cls, name)
        if not _ListboxEventMeta._warned:
            _ListboxEventMeta._warned = True
            warnings.warn(
                "ListboxEvent is deprecated; use EventSeq instead. "
                "Will be removed in v0.5.0.",
                DeprecationWarning,
                stacklevel=2,
            )
        return type.__getattribute__(cls, name)


class ListboxEvent(EventSeq, metaclass=_ListboxEventMeta):
    """Backward-compatible aliases for listbox-level event sequences.

    Deprecated in v0.4.2: use ``EventSeq`` directly for any event constant.
    This class is kept as a thin subclass so existing code keeps working.
    """

    SELECT: Literal["<<ListboxSelect>>"] = "<<ListboxSelect>>"
    KEY_BACKSPACE: Literal["<BackSpace>"] = "<BackSpace>"
    KEY_DELETE: Literal["<Delete>"] = "<Delete>"


ListboxEventLike = EventSeqLike

# Handler signature: receives current state/values dict, returns state update.
ListboxEventHandler = Callable[[dict[str, Any]], dict[str, Any] | None]
# Entry ``events=`` handlers use the same shape (entry values dict → update).
EntryEventHandler = ListboxEventHandler

# Menubar callback: returns a list of top-level item dicts and separator strings.
MenubarCallback = Callable[[], Sequence[dict[str, Any] | str]]


# ── common widget options ──

class CommonWidgetOptions(TypedDict, total=False):
    description: str | None
    takefocus: TakeFocusLike | None
    enabled_if: Callable[[dict[str, Any]], bool] | None
    # Per-widget design-token/style overrides, applied after construction.
    # Keys are widget-native tk/ttk options (``padx``, ``pady``, ``bg``,
    # ``fg``, ``font``, …); values are the native values.
    widget_kwargs: dict[str, Any]


class MenubarItem(TypedDict, total=False):
    label: Required[str]
    command: str
    enabled_if: Callable[[dict[str, Any]], bool] | None
    items: Sequence[dict[str, Any] | str]


class MenubarOptions(TypedDict, total=False):
    items: Sequence[MenubarItem | str]
    description: str | None


class ButtonOptions(CommonWidgetOptions, total=False):
    label: str
    role: str
    state: StateLike
    primary: bool
    font: tuple[str, int] | tuple[str, int, str]


class EntryOptions(CommonWidgetOptions, total=False):
    placeholder: str
    placeholder_as_hint: bool
    role: str
    state: StateLike
    show: str | None
    width: int
    font: tuple[str, int] | tuple[str, int, str]
    padding: int | tuple[int, int] | tuple[int, int, int, int]
    events: dict[str, EntryEventHandler]


class LabelOptions(CommonWidgetOptions, total=False):
    role: str
    font: tuple[str, int] | tuple[str, int, str]
    anchor: str
    justify: str
    padding: int | tuple[int, int]
    width: int


class MessageOptions(CommonWidgetOptions, total=False):
    role: str
    width: int
    auto_width: bool


# ── bind options ──

class BindOptions(CommonWidgetOptions, total=False):
    sequence: Required[str]
    label: str


# ── remaining widget options ──

class CheckbuttonOptions(CommonWidgetOptions, total=False):
    text: str
    key: str
    font: tuple[str, int] | tuple[str, int, str]


class RadiobuttonOptions(CommonWidgetOptions, total=False):
    text: str
    value: str
    group: str
    font: tuple[str, int] | tuple[str, int, str]


class TextOptions(CommonWidgetOptions, total=False):
    width: int
    height: int
    state: StateLike
    tab_inserts: bool
    readonly: bool
    tags: dict[str, dict[str, Any]]
    sync_yscroll_with: str
    font: tuple[str, int] | tuple[str, int, str]
    wrap: WrapLike
    h_scroll: bool


class ScaleOptions(CommonWidgetOptions, total=False):
    key: str
    from_: int
    to: int
    orient: OrientLike


class SpinboxOptions(CommonWidgetOptions, total=False):
    key: str
    from_: float | None
    to: float | None
    values: list[str]
    width: int
    font: tuple[str, int] | tuple[str, int, str]


class ListboxOptions(CommonWidgetOptions, total=False):
    items: list[str]
    items_key: str
    font: tuple[str, int] | tuple[str, int, str]
    selectmode: SelectModeLike
    height: int | None
    events: dict[str, ListboxEventHandler]
    on_update: ListboxSelectCallback


class ComboboxOptions(CommonWidgetOptions, total=False):
    values: list[str]
    values_key: str
    key: str
    width: int
    readonly: bool
    font: tuple[str, int] | tuple[str, int, str]


class TreeviewColumn(TypedDict, total=False):
    id: str
    heading: str
    width: int
    anchor: str
    stretch: bool


class TreeviewOptions(CommonWidgetOptions, total=False):
    columns: Required[list[Any]]
    rows_key: str
    selectmode: SelectModeLike
    height: int
    activate: Callable[[int, list[Any]], dict[str, Any]]
    double_click: bool


class PanedOptions(CommonWidgetOptions, total=False):
    panes: Required[tuple[str, ...] | list[str]]
    orient: OrientLike
    weights: tuple[int, ...] | list[int]
    sashwidth: int


ProgressModeLike = Literal["determinate", "indeterminate"]


class ProgressbarOptions(CommonWidgetOptions, total=False):
    key: str
    maximum: float
    mode: ProgressModeLike
    length: int
    orient: OrientLike


class CanvasOptions(CommonWidgetOptions, total=False):
    width: int
    height: int
    bg: str
    items: list[Any]


FilepickerModeLike = Literal["open", "save", "directory", "open_multiple"]


class FilepickerOptions(CommonWidgetOptions, total=False):
    mode: FilepickerModeLike
    title: str
    initialdir: str
    initialfile: str
    filetypes: Sequence[tuple[str, str]]
    defaultextension: str
    multiple: bool
    label: str
    primary: bool
    font: tuple[str, int] | tuple[str, int, str]
    state: StateLike




__all__ = [
    "Anchor",
    "AnchorLike",
    "BindOptions",
    "ButtonCallback",
    "ButtonOptions",
    "CanvasOptions",
    "CheckbuttonOptions",
    "CommonWidgetOptions",
    "EntryEventHandler",
    "EntryOptions",
    "EventSeq",
    "EventSeqLike",
    "ExpandLike",
    "FilepickerCallback",
    "FilepickerModeLike",
    "FilepickerOptions",
    "Fill",
    "FillLike",
    "Justify",
    "JustifyLike",
    "LabelCallback",
    "LabelOptions",
    "ListboxEvent",
    "ListboxEventHandler",
    "ListboxEventLike",
    "ListboxOptions",
    "MenubarCallback",
    "MenubarItem",
    "MenubarOptions",
    "MessageOptions",
    "Orient",
    "OrientLike",
    "PanedOptions",
    "primary_button_release",
    "primary_click",
    "primary_double_click",
    "ProgressModeLike",
    "ProgressbarOptions",
    "RadiobuttonOptions",
    "Relief",
    "ReliefLike",
    "ScaleOptions",
    "SelectMode",
    "SelectModeLike",
    "Side",
    "SideLike",
    "SpinboxOptions",
    "State",
    "StateLike",
    "Sticky",
    "StickyLike",
    "TakeFocus",
    "TakeFocusLike",
    "TextOptions",
    "TreeviewActivateCallback",
    "TreeviewColumn",
    "TreeviewOptions",
    "TreeviewSelectCallback",
    "Wrap",
    "WrapLike",
]
