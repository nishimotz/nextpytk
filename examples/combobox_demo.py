"""nextpytk combobox demo — email folder and priority selectors.

Two ttk.Combobox widgets: an editable folder selector (so the user can
enter a new folder name) and a read-only priority picker. Choices update
a status label.
"""

from __future__ import annotations

from nextpytk import Layout, TkApp
from nextpytk.types import Fill

app = TkApp(title="Combobox demo")

FOLDERS = ["INBOX", "Sent", "Drafts", "Archive", "Trash"]
PRIORITIES = ["Low", "Normal", "High", "Urgent"]


@app.status("info")
def info() -> str:
    return "Select a folder and priority"


@app.combobox("folder", values=FOLDERS)
def on_folder(value: str) -> dict[str, str]:
    return {"info": f"Folder: {value}"}


@app.combobox("priority", values=PRIORITIES, readonly=True)
def on_priority(value: str) -> dict[str, str]:
    return {"info": f"Priority: {value}"}


layout = (
    Layout()
    .section("info")
    .section("folder", fill=Fill.X)
    .section("priority", fill=Fill.X)
)


if __name__ == "__main__":
    app.run(layout=layout, geometry="320x160")
