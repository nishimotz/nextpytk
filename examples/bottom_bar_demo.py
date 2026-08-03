"""Fixed bottom section demo — ``section(..., side="bottom")``.

Demonstrates that a ``side="bottom"`` section stays pinned to the bottom of
the window even when a preceding ``expand=True`` block (the body) grows to
fill the remaining vertical space.

Before this behavior was fixed, the section frame was always packed with
``side="top"`` regardless of the requested side, so a bottom bar placed after
an expandable body was pushed off-view (collapsed to 1x1).

Resize the window vertically: the body stretches and the bottom bar stays
visible at the bottom edge.
"""

from nextpytk import TkApp, Layout

app = TkApp(title="Fixed Bottom Bar")


@app.label("body")
def body() -> str:
    return "Resize the window vertically - the bottom bar stays pinned."


@app.label("bottom_bar")
def bottom_bar() -> str:
    return "I am pinned to the bottom edge."


if __name__ == "__main__":
    app.run(
        layout=(
            Layout()
            .section("body", fill="both", expand=True)
            # ``side="bottom"`` keeps this bar at the window's bottom edge
            # regardless of how tall the expandable body above grows.
            .section("bottom_bar", side="bottom", fill="x")
        ),
        geometry="460x320",
    )
