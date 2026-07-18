"""Tab focus demo — ``takefocus`` on nextpytk widgets.

Tab through the form: name → email → agree → submit.
The hint label and status line are skipped (``takefocus=0``).

Focus ring — Tcl/Tk notes
-----------------------------

* **Classic tk** (``tk.Entry`` etc.): ``-highlightthickness`` /
  ``-highlightcolor`` is the traversal highlight (options manual).
* **ttk**: ``-highlightthickness`` is not supported. Each OS's Aqua / Windows / GTK
  theme draws the keyboard-focus ring (e.g. macOS 8.6.14 light mode uses
  ``kThemeAdornmentFocus``; Entry gets a blue-cyan ring).
* **macOS dark mode**: Button / Checkbutton may have weak or no focus ring
  (``DrawDarkButton`` path). If needed, handle it in the app separately.
* **takefocus**: Tab traversal is controlled by ``TakeFocus`` / ``takefocus=``.
"""

from __future__ import annotations

from nextpytk import Layout, TkApp
from nextpytk.types import TakeFocus

app = TkApp(title="Tab focus — takefocus demo")

layout = (
    Layout()
    .section("hint")
    .section("name", "email")
    .section("agree")
    .section("submit")
    .section("status")
)


@app.label("hint", takefocus=TakeFocus.NO)
def hint():
    return "Tab through name → email → agree → submit in order"


@app.entry("name", placeholder="Name", takefocus=TakeFocus.YES)
def name(value: str):
    return {"status": f"name: {value!r}"}


@app.entry("email", placeholder="Email", takefocus=TakeFocus.YES)
def email(value: str):
    return {"status": f"email: {value!r}"}


@app.checkbutton("agree", text="Agree", takefocus=TakeFocus.YES)
def agree(checked: bool):
    return {"status": f"agree: {checked}"}


@app.button("submit", label="Submit", takefocus=TakeFocus.YES)
def submit(_vals):
    return {"status": "submitted"}


@app.status("status", takefocus=TakeFocus.NO)
def status():
    return str(app.state.get("status", "—"))


if __name__ == "__main__":
    app.run(layout=layout)
