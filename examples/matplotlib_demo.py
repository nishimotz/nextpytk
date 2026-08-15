"""nextpytk + Matplotlib integration demo.

Embeds a Matplotlib plot into a nextpytk app via ``Layout.container()`` and
``app.container()``. Demonstrates the official pattern for mixing nextpytk's
declarative widgets with an imperative third-party canvas:

- ``Layout().container("plot")`` reserves a themed, unmanaged ``tk.Frame``.
- ``on_ready`` mounts a ``FigureCanvasTkAgg`` into that frame.
- A ``@app.scale`` drives the plot reactively: the scale callback redraws the
  plot via ``canvas.draw_idle()``.

Run with the optional ``matplotlib`` extra:

    uv run --extra matplotlib -- python examples/matplotlib_demo.py

Key points (see hello-tkinter-tcl's matplotlib-integration-guide):
- Use the object-oriented ``Figure`` API, never ``pyplot`` / ``plt.show()``
  (which would fight Tk's own mainloop).
- Redraw with ``canvas.draw_idle()``, not ``draw()``, to keep the UI responsive.
- Pack the canvas widget with ``fill="both", expand=True`` so it resizes.
"""

from __future__ import annotations

import sys

from nextpytk import Layout, TkApp
from nextpytk.types import Fill

try:
    import numpy as np
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except ImportError as err:  # pragma: no cover - depends on optional extra
    print(
        f"Missing optional dependency: {err}\n"
        "Run with the matplotlib extra:\n"
        "    uv run --extra matplotlib -- python examples/matplotlib_demo.py",
        file=sys.stderr,
    )
    sys.exit(1)

app = TkApp(title="nextpytk + Matplotlib")

# Mounted in _init_plot (on_ready), read by _redraw_plot.
_ax = None
_canvas = None


@app.label("title", role="heading")
def title() -> str:
    return "Sine wave (Matplotlib embedded via container())"


@app.scale("freq", from_=1, to=10)
def on_freq(value: int) -> dict:
    # The framework already wrote state["freq"] before this callback runs,
    # so we can redraw directly from state.
    _redraw_plot()
    return {}


@app.status("hint")
def hint() -> str:
    return "Drag the slider to change the frequency"


layout = (
    Layout()
    .section("title")
    .section("freq")
    .section("hint")
    .container("plot", fill=Fill.BOTH, expand=True)
)


def _redraw_plot() -> None:
    """Redraw the embedded plot from current app state."""
    if _ax is None or _canvas is None:
        return
    freq = float(app._state.get("freq", 1))
    x = np.linspace(0, 10, 400)
    y = np.sin(freq * x)
    _ax.clear()
    _ax.plot(x, y, color="#7a5a34")
    _ax.set_title(f"sin({freq:.1f} x)")
    _ax.grid(True)
    _canvas.draw_idle()


def _init_plot(_app: TkApp) -> None:
    """Mount the Matplotlib canvas into the reserved container frame."""
    global _ax, _canvas
    frame = app.container("plot")
    fig = Figure(figsize=(5, 3), dpi=100)
    _ax = fig.add_subplot(111)
    _canvas = FigureCanvasTkAgg(fig, master=frame)
    _canvas.get_tk_widget().pack(fill="both", expand=True)
    _redraw_plot()


if __name__ == "__main__":
    app.run(layout=layout, geometry="640x480", on_ready=_init_plot)
