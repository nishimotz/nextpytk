"""nextpytk widget gallery — all widgets via ``with app.view(name):``."""

from nextpytk import TkApp, Layout

app = TkApp(title="Widget Gallery — nextpytk")


INITIAL_STATE: dict[str, str] = {
    "tab": "Button",
    "msg": "",
    "btn_msg": "状態: 待機中",
    "color": "",
    "c_msg": "☐ 未同意",
    "lb_msg": "選択: なし",
    "e_mirror_text": "↑ ここに反映",
    "t_info": "",
    "s_h_val": "0",
    "s_v_val": "0",
    "sp_num": "0",
}


def _get_state(key: str, default: str = "") -> str:
    return str(app.state.get(key, default))


# ─── Status bar ───

@app.status("title", description="current tab")
def title():
    return f"🎯 {_get_state('tab')}"


@app.status("msg", description="feedback")
def msg():
    return _get_state("msg")


# ─── Tab switcher buttons ───

TAB_NAMES = [
    "Button", "Label", "Entry", "Text", "Checkbutton",
    "Radiobutton", "Canvas", "Scale", "Message", "Spinbox", "Listbox",
]


# ─── Views (tab content) ───

# Each ``with app.view(tab_name) as v:`` block registers all widgets
# for that tab. Use ``app.view_widget_names(tab_name)`` at runtime.

with app.view(
    "Button",
    layout=Layout().section("b_status").section("b_click", "b_ok"),
) as v:
    @v.status("b_status", description="state")
    def b_status():
        return _get_state("btn_msg", "状態: 待機中")

    @v.button("b_click", label="クリックしてね")
    def b_click(vals):
        return {"btn_msg": "状態: クリックされました！"}

    @v.button("b_ok", label="OK")
    def b_ok(vals):
        return {"btn_msg": "状態: OK!"}


with app.view(
    "Label",
    layout=Layout().section("l_normal").section("l_large").section("l_right"),
) as v:
    @v.label("l_normal")
    def l_normal(): return "これは通常のラベルです"

    @v.label("l_large", font=("TkDefaultFont", 18, "bold"), padding=4)
    def l_large(): return "これは大きめのラベルです"

    @v.label("l_right", anchor="e", justify="right")
    def l_right(): return "右寄せラベル"


with app.view(
    "Entry",
    layout=(
        Layout()
        .section("e_mirror")
        .section("e_input")
        .section("e_reflect", "e_pwlen")
        .section("e_pw")
    ),
) as v:
    @v.status("e_mirror")
    def e_mirror():
        return _get_state("e_mirror_text", "↑ ここに反映")

    @v.entry("e_input", placeholder="テキストを入力")
    def on_e_input(value):
        if value:
            return {"e_mirror_text": f"入力内容: {value}"}
        return {"e_mirror_text": "↑ ここに反映"}

    @v.button("e_reflect", label="入力クリア")
    def e_reflect(vals):
        return {"e_input": "", "e_mirror_text": "↑ ここに反映"}

    @v.entry("e_pw", placeholder="パスワード", show="*")
    def on_e_pw(value): return {}

    @v.button("e_pwlen", label="パスワード長確認")
    def e_pwlen(vals):
        pw = vals.get("e_pw", "")
        return {"e_mirror_text": f"パスワード長: {len(pw)}"}


with app.view(
    "Text",
    layout=Layout().section("t_editor", fill="both", expand=True).section("t_info"),
) as v:
    @v.text("t_editor", width=50, height=8)
    def on_text(value):
        lines = len(value.split("\n"))
        return {"t_info": f"文字数: {len(value)}, 行数: {lines}"}

    @v.status("t_info")
    def t_info():
        return _get_state("t_info")


with app.view(
    "Checkbutton",
    layout=Layout().section("c_agree", fill="none").section("c_msg"),
) as v:
    @v.checkbutton("c_agree", text="同意します", key="c_val")
    def on_check(on: bool):
        return {"c_msg": "✅ 同意" if on else "☐ 未同意"}

    @v.status("c_msg")
    def c_msg():
        return _get_state("c_msg", "☐ 未同意")


with app.view(
    "Radiobutton",
    layout=(
        Layout()
        .section("r_red", fill="none")
        .section("r_blue", fill="none")
        .section("r_green", fill="none")
        .section("r_msg")
    ),
) as v:
    @v.radiobutton("r_red", text="赤", value="red", group="color")
    def on_red(val): return {}

    @v.radiobutton("r_blue", text="青", value="blue", group="color")
    def on_blue(val): return {}

    @v.radiobutton("r_green", text="緑", value="green", group="color")
    def on_green(val): return {}

    @v.status("r_msg")
    def r_msg():
        c = _get_state("color")
        return f"選択色: {c}" if c else "選択してください"


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
                   {"text": "Canvas デモ", "font": ("TkDefaultFont", 14)}),
              ])
    def _cv_noop(): return


with app.view(
    "Scale",
    layout=(
        Layout()
        .section("s_h")
        .section("s_v", fill="none")
        .section("s_info")
    ),
) as v:
    @v.scale("s_h", key="s_h_val", from_=0, to=100, orient="horizontal")
    def on_scale_h(val): return {}

    @v.scale("s_v", key="s_v_val", from_=0, to=100, orient="vertical")
    def on_scale_v(val): return {}

    @v.status("s_info")
    def s_info():
        h = _get_state("s_h_val", "0")
        v = _get_state("s_v_val", "0")
        return f"水平: {h}, 垂直: {v}"


with app.view(
    "Message",
    layout=Layout().section("m_text", fill="both", expand=True),
) as v:
    @v.message("m_text")
    def m_text():
        return ("message ウィジェットは、長いテキストを自動的に折り返します。"
                "複数行にまたがる文章を表示するのに適しています。"
                "label との違いは、自動折り返し機能にあります。")


with app.view(
    "Spinbox",
    layout=(
        Layout()
        .section("sp_num_lbl")
        .section("sp_num", fill="none")
        .section("sp_summary")
    ),
) as v:
    @v.label("sp_num_lbl")
    def sp_num_lbl(): return "数値選択 (0-100):"

    @v.spinbox("sp_num", key="sp_num", from_=0, to=100)
    def on_sp_num(val): return {}

    @v.status("sp_summary")
    def sp_summary():
        num = _get_state("sp_num")
        return f"数値: {num}"


with app.view(
    "Listbox",
    layout=Layout().section("lb_items", fill="both", expand=True).section("lb_msg"),
) as v:
    @v.listbox("lb_items",
               items=["項目1", "項目2", "項目3", "項目4", "項目5",
                      "項目6", "項目7", "項目8"])
    def on_lb(val):
        return {"lb_msg": f"選択: {val}" if val else "選択: なし"}

    @v.status("lb_msg")
    def lb_msg():
        return _get_state("lb_msg", "選択: なし")


@app.multiview(
    "gallery",
    views=TAB_NAMES,
    toplevel_widgets=("title", "msg"),
    initial_state=INITIAL_STATE,
    on_tab_change=lambda tab: {"tab": tab, "msg": ""},
)
def gallery_multiview() -> None:
    """Notebook declaration for the widget gallery."""


if __name__ == "__main__":
    app.run(multiview="gallery")
