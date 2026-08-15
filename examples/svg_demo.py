"""nextpytk SVG image demo (requires Tk 9.0+).

Demonstrates loading an SVG image with ``tk.PhotoImage`` and displaying it in
a nextpytk app. SVG support was added in Tk 9.0, so this example checks the
runtime Tcl/Tk version and exits with a clear message on older Tk (8.6).

Run with a Python that bundles Tk 9.0+ (e.g. the official python.org 3.14
installer):

    uv run --python 3.14 python examples/svg_demo.py

Key points (see hello-tkinter-tcl's image-handling-guide):
- ``PhotoImage`` reads SVG only on Tk 9.0+; PNG needs Tk 8.6+.
- Keep a reference to the ``PhotoImage`` (here ``app._images``) or it is
  garbage-collected and the image disappears.
- ``PhotoImage(data=...)`` accepts raw SVG text, so no external file is needed.
"""

from __future__ import annotations

import sys
import tkinter as tk

from nextpytk import Layout, TkApp

# A small self-contained SVG (no external file dependency).
_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
  <rect width="200" height="200" rx="16" fill="#7a5a34"/>
  <circle cx="100" cy="100" r="60" fill="#efc53e"/>
  <text x="100" y="112" font-size="48" text-anchor="middle" fill="#302b24">SVG</text>
</svg>
"""


def _tk_version() -> tuple[int, int]:
    """Return the runtime Tcl/Tk version as (major, minor)."""
    try:
        patch = tk.Tcl().eval("info patchlevel")  # e.g. "9.0.4"
        major, minor = (int(x) for x in patch.split(".")[:2])
        return major, minor
    except Exception:
        return (0, 0)


def _require_tk9() -> None:
    """Exit with a clear message when SVG support (Tk 9.0+) is unavailable."""
    major, minor = _tk_version()
    if (major, minor) < (9, 0):
        print(
            f"SVG images require Tk 9.0+ (found Tk {major}.{minor}).\n"
            "Install a Python that bundles Tk 9.0+ (e.g. the official "
            "python.org 3.14 installer) and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)


_require_tk9()

app = TkApp(title="nextpytk SVG demo")


@app.label("title", role="heading")
def title() -> str:
    return "SVG image (Tk 9.0+)"


@app.status("hint")
def hint() -> str:
    return "The image below is an inline SVG rendered by tk.PhotoImage"


layout = (
    Layout()
    .section("title")
    .section("hint")
    .container("image_slot")
)


def _mount_image(_app: TkApp) -> None:
    """Load the SVG and display it in the reserved container frame."""
    frame = app.container("image_slot")
    img = tk.PhotoImage(data=_SVG)
    # Keep a reference so the image is not garbage-collected.
    app._images = getattr(app, "_images", {})
    app._images["logo"] = img
    label = tk.Label(frame, image=img, bg=app.theme_tokens.bg)
    label.pack(padx=8, pady=8)


if __name__ == "__main__":
    app.run(layout=layout, geometry="360x360", on_ready=_mount_image)
