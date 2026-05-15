"""Fluent DSL types for Layout: tkinter constants exposed as typed class constants.

Each type (Side, Fill, Sticky, …) is a class with class-level constants
that double as Literal type annotations. Pyright/mypy validate both the
value and the type through the same name.

Usage::

    from tkouter.types import Side, Fill
    Layout().section("msg", side=Side.LEFT, fill=Fill.X)
"""

from __future__ import annotations

from typing import Literal


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
