"""nextpytk widget gallery — all widgets via ``with app.view(name):``."""

from nextpytk import TkApp, Layout
from nextpytk.types import Fill, Sticky

app = TkApp(title="Widget Gallery — nextpytk")


INITIAL_STATE: dict[str, str] = {
    "tab": "Button",
    "msg": "",
    "color": "",
    "e_mirror_text": "↑ reflected here",
    "t_info": "",
    "s_h_val": "0",
    "s_v_val": "0",
    "sp_num": "0",
}


def _get_state(key: str, default: str = "") -> str:
    return str(app.state.get(key, default))


# ─── Chrome header and shared bottom status bar ───

@app.status("title", description="current tab")
def title():
    return f"🎯 {_get_state('tab')}"


@app.status("msg", description="feedback")
def msg():
    return _get_state("msg")


# ─── Tab switcher buttons ───

TAB_NAMES = [
    "Button", "Label", "Entry", "Text", "Checkbutton",
    "Radiobutton", "Canvas", "Scale", "Message", "Spinbox",
    "Combobox", "Listbox",
]


# ─── Views (tab content) ───

# Each ``with app.view(tab_name) as v:`` block registers all widgets
# for that tab. Use ``app.view_widget_names(tab_name)`` at runtime.

with app.view(
    "Button",
    layout=(
        Layout()
        .grid(fill=Fill.BOTH, expand=True, uniform="buttons")
            .col_weight(0, 1)
            .col_weight(1, 1)
            .widget("b_primary", sticky=Sticky.EW)
            .widget("b_secondary", sticky=Sticky.EW)
            .next_row()
            .widget("b_click", sticky=Sticky.EW)
            .widget("b_ok", sticky=Sticky.EW)
            .end_grid()
    ),
) as v:
    @v.button("b_primary", label="Primary button", primary=True)
    def b_primary(vals):
        return {"msg": "State: primary button pressed"}

    @v.button("b_secondary", label="Secondary button")
    def b_secondary(vals):
        return {"msg": "State: secondary button pressed"}

    @v.button("b_click", label="Click me")
    def b_click(vals):
        return {"msg": "State: clicked!"}

    @v.button("b_ok", label="OK")
    def b_ok(vals):
        return {"msg": "State: OK!"}


with app.view(
    "Label",
    layout=Layout().section("l_normal", fill=Fill.NONE).section("l_large", fill=Fill.NONE).section("l_right", fill=Fill.NONE),
) as v:
    @v.label("l_normal")
    def l_normal(): return "This is a normal label"

    @v.label("l_large", font=("TkDefaultFont", 18, "bold"), padding=4)
    def l_large(): return "This is a large label"

    @v.label("l_right")
    def l_right(): return "Left-aligned label"


with app.view(
    "Entry",
    layout=(
        Layout()
        .section("e_input", fill=Fill.NONE)
        .section("e_reflect", "e_pwlen", fill=Fill.NONE)
        .section("e_pw", fill=Fill.NONE)
    ),
) as v:
    @v.entry("e_input", placeholder="Enter text")
    def on_e_input(value):
        if value:
            return {"msg": f"Input: {value}"}
        return {"msg": "↑ reflected here"}

    @v.button("e_reflect", label="Clear input")
    def e_reflect(vals):
        return {"e_input": "", "msg": "↑ reflected here"}

    @v.entry("e_pw", placeholder="Password", show="*")
    def on_e_pw(value): return {}

    @v.button("e_pwlen", label="Check password length")
    def e_pwlen(vals):
        pw = vals.get("e_pw", "")
        return {"msg": f"Password length: {len(pw)}"}


with app.view(
    "Text",
    layout=Layout().section("t_editor", fill=Fill.BOTH, expand=True),
) as v:
    @v.text("t_editor", width=50, height=8)
    def on_text(value):
        lines = len(value.split("\n"))
        return {"msg": f"Characters: {len(value)}, Lines: {lines}"}


def _init_text_demo(_app: TkApp) -> None:
    sample = "\n".join(f"Line {i}: widget gallery text demo content" for i in range(1, 31))
    _app.text_set("t_editor", sample)


with app.view(
    "Checkbutton",
    layout=Layout().section("c_agree", fill=Fill.NONE),
) as v:
    @v.checkbutton("c_agree", text="I agree", key="c_val")
    def on_check(on: bool):
        return {"msg": "✅ Agreed" if on else "☐ Not agreed"}


with app.view(
    "Radiobutton",
    layout=(
        Layout()
        .section("r_red", "r_blue", "r_green", fill=Fill.NONE)
    ),
) as v:
    @v.radiobutton("r_red", text="Red", value="red", group="color")
    def on_red(val):
        return {"msg": f"Selected color: {val}"}

    @v.radiobutton("r_blue", text="Blue", value="blue", group="color")
    def on_blue(val):
        return {"msg": f"Selected color: {val}"}

    @v.radiobutton("r_green", text="Green", value="green", group="color")
    def on_green(val):
        return {"msg": f"Selected color: {val}"}


with app.view(
    "Canvas",
    layout=Layout().section("cv_demo", fill="both", expand=True),
) as v:
    @v.canvas("cv_demo", width=300, height=200, bg="#f0f0f0",
              items=[
                  ("rectangle", 20, 20, 120, 80, {"fill": "blue"}),
                  ("oval", 150, 20, 250, 80, {"fill": "red"}),
                  ("line", 20, 120, 280, 120, {"fill": "green", "width": 3}),
                  ("text", 150, 170,
                   {"text": "Canvas demo", "font": ("TkDefaultFont", 14),
                    "fill": "#1a1a1a"}),
              ])
    def _cv_noop(): return


with app.view(
    "Scale",
    layout=(
        Layout()
        .section("s_h")
        .section("s_v", fill=Fill.NONE)
    ),
) as v:
    @v.scale("s_h", key="s_h_val", from_=0, to=100, orient="horizontal")
    def on_scale_h(val):
        return {"msg": f"Horizontal scale: {val}"}

    @v.scale("s_v", key="s_v_val", from_=0, to=100, orient="vertical")
    def on_scale_v(val):
        return {"msg": f"Vertical scale: {val}"}


with app.view(
    "Message",
    layout=Layout().section("m_text", fill=Fill.BOTH, expand=True),
) as v:
    @v.message("m_text")
    def m_text():
        return ("The message widget automatically wraps long text. "
                "It is suitable for displaying sentences spanning multiple lines. "
                "The difference from label is the auto-wrap feature.")


with app.view(
    "Spinbox",
    layout=(
        Layout()
        .section("sp_num_lbl", "sp_num", fill=Fill.NONE)
    ),
) as v:
    @v.label("sp_num_lbl")
    def sp_num_lbl(): return "Number selection (0-100):"

    @v.spinbox("sp_num", key="sp_num", from_=0, to=100, width=6)
    def on_sp_num(val):
        return {"msg": f"Number: {val}"}


with app.view(
    "Combobox",
    layout=Layout().section("cb_label", fill=Fill.NONE).section("cb_demo", fill=Fill.NONE),
) as v:
    @v.label("cb_label")
    def cb_label(): return "Select a profile:"

    @v.combobox("cb_demo",
                values=["Default", "Developer", "Designer", "Reviewer"],
                readonly=True)
    def on_cb(value):
        return {"msg": f"Profile: {value}"}


with app.view(
    "Listbox",
    layout=Layout().section("lb_items", fill=Fill.BOTH, expand=True),
) as v:
    @v.listbox("lb_items",
               items=["Item 1", "Item 2", "Item 3", "Item 4", "Item 5",
                      "Item 6", "Item 7", "Item 8"])
    def on_lb(idx):
        return {"msg": f"Selected: item {idx}" if idx >= 0 else "Selected: none"}


@app.multiview(
    "gallery",
    views=TAB_NAMES,
    toplevel_widgets=("title", "msg"),
    initial_state=INITIAL_STATE,
    on_tab_change=lambda tab: {"tab": tab, "msg": ""},
    tabposition="w",
)
def gallery_multiview() -> None:
    """Notebook declaration for the widget gallery."""


if __name__ == "__main__":
    app.run(multiview="gallery", on_ready=_init_text_demo)
