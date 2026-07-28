"""Minimal menubar demo: File menu with enabled_if-driven Save item.

Note: on macOS (Aqua) the menubar is rendered at the top of the screen,
inside the system menu bar, not inside the window. On Windows / X11 it
appears just below the window title bar.
"""

from nextpytk import TkApp, Layout

app = TkApp(title="Menubar Demo — nextpytk")


@app.filepicker("m_open", mode="open", title="Open file",
                filetypes=[("Text files", "*.txt"), ("All files", "*")])
def m_open(path):
    return {"msg": f"Opened: {path}", "dirty": True}


@app.menubar("menu")
def menu_bar():
    return [
        {
            "label": "File",
            "items": [
                {"label": "New", "command": "m_new"},
                {"label": "Open...", "command": "m_open"},
                {"label": "Save", "command": "m_save",
                 "enabled_if": lambda vals: bool(vals.get("dirty"))},
                "---",
                {"label": "Exit", "command": "m_exit"},
            ],
        },
    ]


@app.button("m_new")
def m_new(vals):
    return {"msg": "New file", "dirty": True}


@app.button("m_save")
def m_save(vals):
    return {"msg": "Saved", "dirty": False}


@app.button("m_exit")
def m_exit(vals):
    return {"msg": "Exit selected"}


@app.status("msg")
def msg():
    return app.state.get("msg", "Use the menu above")


app.run(
    layout=Layout.from_list(["msg"]),
    initial_state={"dirty": False},
)
