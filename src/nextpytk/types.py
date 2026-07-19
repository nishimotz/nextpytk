"""Fluent DSL types for Layout: tkinter constants exposed as typed class constants.

Each type (Side, Fill, Sticky, …) is a class with class-level constants
that double as Literal type annotations. Pyright/mypy validate both the
value and the type through the same name.

Usage::

    from nextpytk.types import Side, Fill
    Layout().section("msg", side=Side.LEFT, fill=Fill.X)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
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

# ── listbox event sequences (widget-level bind) ──

class ListboxEvent:
    """Common event sequences for ``@app.listbox(..., events=...)``.

    Use these constants for IDE completion and typo protection; arbitrary
    tkinter event strings are still accepted at runtime.
    """

    SELECT: Literal["<<ListboxSelect>>"] = "<<ListboxSelect>>"
    RETURN: Literal["<Return>"] = "<Return>"
    DOUBLE_CLICK: Literal["<Double-Button-1>"] = "<Double-Button-1>"
    KEY_BACKSPACE: Literal["<BackSpace>"] = "<BackSpace>"
    KEY_DELETE: Literal["<Delete>"] = "<Delete>"

ListboxEventLike = Literal[
    "<<ListboxSelect>>",
    "<Return>",
    "<Double-Button-1>",
    "<BackSpace>",
    "<Delete>",
]

# Handler signature: receives current state dict, returns state update dict.
ListboxEventHandler = Callable[[dict[str, Any]], dict[str, Any] | None]

# Menubar callback: returns a list of top-level item dicts and separator strings.
MenubarCallback = Callable[[], Sequence[dict[str, Any] | str]]


# ── common widget options ──

class CommonWidgetOptions(TypedDict, total=False):
    description: str | None
    takefocus: TakeFocusLike | None
    enabled_if: Callable[[dict[str, Any]], bool] | None


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
    font: tuple[str, int] | tuple[str, int, str]
    selectmode: SelectModeLike
    height: int | None
    events: dict[str, ListboxEventHandler]
    on_update: ListboxSelectCallback


class ComboboxOptions(CommonWidgetOptions, total=False):
    values: list[str]
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




__all__ = [
    "Anchor",
    "AnchorLike",
    "BindOptions",
    "ButtonCallback",
    "ButtonOptions",
    "CanvasOptions",
    "CheckbuttonOptions",
    "CommonWidgetOptions",
    "EntryOptions",
    "ExpandLike",
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
]
