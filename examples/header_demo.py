"""Layout chrome demo — ``.header()`` title block and ``.status()`` bottom bar.

``Layout.header(title, subtitle)`` renders a Kizashi window header.
``Layout.status(name)`` places the ``@app.status(name)`` widget in a styled
bottom status bar (2px rule + muted left-aligned text).
"""

from nextpytk import TkApp, Layout

app = TkApp(title="Header Demo")


@app.entry("name", placeholder="Your name")
def on_name(value: str) -> dict:
    return {}


@app.button("greet", label="Greet")
def on_greet(values: dict) -> dict:
    who = values.get("name", "").strip() or "stranger"
    return {"status_bar": f"Hello, {who}!"}


@app.status("status_bar", description="greeting feedback")
def status_bar() -> str:
    return "Enter your name and press the button"


if __name__ == "__main__":
    app.run(
        layout=(
            Layout()
            .header("Header Demo", "Minimal example of Layout().header() / .status()")
            .section("name")
            .section("greet")
            .status("status_bar")
        ),
    )
