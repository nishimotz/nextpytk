"""nextpytk multi-screen sample: simple order-taking UI.

- Several widget kinds (label, button, entry; more can be added)
- Extra state besides on-screen text (counter, list, selection, screen id)
- Screen switching by rebuilding layout under one ``Tk``
- Mix of ``Layout.section`` (pack) and ``Layout.grid`` (grid)

State keys:
  - counter: int (order count)
  - items: list[str] (ordered items)
  - screen: str ("menu" | "confirm" | "thanks")
  - selected: str (current menu pick)
  - msg: str (feedback line)
"""

import tkinter as tk
from tkinter import ttk
from nextpytk import TkApp, Layout

app = TkApp(title="注文管理")

# --- Initial state ---
_state: dict = {
    "counter": 0,
    "items": [],
    "screen": "menu",
    "selected": "",
    "msg": "",
}


def _get(key: str):
    return _state.get(key, "")


def _set(**kw):
    _state.update(kw)
    app._apply_state({k: v for k, v in kw.items() if k in app._tk_widgets})


# --- Labels ---

@app.label("title", role="heading")
def title():
    return "🍜 注文カウンター"


@app.label("menu_lbl")
def menu_lbl():
    return f"メニュー: {_get('counter')} 杯目"


@app.status("selected_lbl")
def selected_lbl():
    sel = _state.get("selected", "")
    return f"選択中: {sel}" if sel else "メニューを選んでください"


@app.label("items_lbl")
def items_lbl():
    lst = _state.get("items", [])
    if not lst:
        return "注文履歴: (なし)"
    return "注文履歴:\n" + "\n".join(f"  {i+1}. {x}" for i, x in enumerate(lst))


@app.label("result_lbl")
def result_lbl():
    return _state.get("msg", "")


# --- Menu buttons ---

@app.button("ramen", label="🍜 ラーメン")
def on_ramen(vals):
    _set(selected="ラーメン", msg="ラーメンを選択しました")
    return {}


@app.button("gyoza", label="🥟 餃子")
def on_gyoza(vals):
    _set(selected="餃子", msg="餃子を選択しました")
    return {}


@app.button("rice", label="🍚 ライス")
def on_rice(vals):
    _set(selected="ライス", msg="ライスを選択しました")
    return {}


@app.button("add", label="✅ 追加")
def on_add(vals):
    sel = _state.get("selected", "")
    if not sel:
        _set(msg="先にメニューを選んでください")
        return {}
    items = list(_state.get("items", []))
    items.append(sel)
    cnt = _state.get("counter", 0) + 1
    _set(items=items, counter=cnt, msg=f"{sel} を追加しました (計{cnt}杯)", selected="")
    return {}


@app.button("confirm", label="📋 確認画面へ")
def on_confirm(vals):
    items = _state.get("items", [])
    if not items:
        _set(msg="注文がありません")
        return {}
    _set(screen="confirm", msg="")
    return {}


@app.button("back", label="← メニューに戻る")
def on_back(vals):
    _set(screen="menu", msg="")
    return {}


@app.button("submit", label="👍 注文確定")
def on_submit(vals):
    cnt = _state.get("counter", 0)
    _set(screen="thanks", msg=f"ありがとうございます！ {cnt}杯ご注文確定")
    return {}


@app.button("reset", label="🔄 最初から")
def on_reset(vals):
    _set(counter=0, items=[], selected="", screen="menu", msg="リセットしました")
    return {}


# --- Extra screens (labels only on confirm/thanks) ---

@app.label("confirm_title", role="heading")
def confirm_title():
    return "📋 注文確認"


@app.label("confirm_items")
def confirm_items():
    lst = _state.get("items", [])
    if not lst:
        return "(注文なし)"
    return "\n".join(f"  {i+1}. {x}" for i, x in enumerate(lst))


@app.label("thanks_title", role="heading")
def thanks_title():
    return "✅ ご注文ありがとうございました！"


@app.label("thanks_summary")
def thanks_summary():
    cnt = _state.get("counter", 0)
    lst = _state.get("items", [])
    return f"{cnt}杯のご注文を承りました。\n内訳:\n" + "\n".join(f"  {i+1}. {x}" for i, x in enumerate(lst))


# --- Layout factory per screen ---


def layout_for(screen: str) -> Layout:
    if screen == "menu":
        return (
            Layout()
            .section("title")
            .section("menu_lbl")
            .grid()
            .at(0, 0).widget("ramen").widget("gyoza")
            .next_row().widget("rice").end_grid()
            .section("selected_lbl")
            .section("add", "confirm")
            .section("items_lbl")
            .section("result_lbl")
        )
    elif screen == "confirm":
        return (
            Layout()
            .section("confirm_title")
            .section("confirm_items")
            .section("back", "submit")
            .section("reset")
        )
    elif screen == "thanks":
        return (
            Layout()
            .section("thanks_title")
            .section("thanks_summary")
            .section("reset")
        )
    return Layout()


# --- Custom flow: rebuild UI on screen change (not TkApp.run) ---

_original_run = app.run


def run_with_screens(*, root: tk.Tk | None = None, layout: Layout | None = None):
    if root is not None:
        app._root = root
    if app._root is None:
        app._root = tk.Tk()
        app._root.title(app._title)
    screen = _state.get("screen", "menu")
    _pack_screen(app, screen)


def _pack_screen(app: TkApp, screen: str) -> None:
    """Tear down and rebuild the UI for ``screen`` (avoids pack/grid on the same root parent)."""
    root = app._root
    if root is None:
        raise RuntimeError("Tk root is not initialized")
    for child in list(root.winfo_children()):
        child.destroy()

    app._tk_widgets = {}
    app._tk_vars = {}
    app._widget_masters = {}
    app._row_pack_jobs = []
    app._grid_pack_jobs = []

    L = layout_for(screen)
    L.mount_frames(app)
    app._build_widgets()
    L.pack_children(app)
    app._sync_widgets()
    app._sync_widget_states()


# Re-bind after button handlers to refresh layout for the new screen.
_original_on_click = app._on_button_click


def _patched_on_click(spec, fn):
    _original_on_click(spec, fn)
    screen = _state.get("screen", "menu")
    _pack_screen(app, screen)


app._on_button_click = _patched_on_click  # type: ignore[method-assign]


if __name__ == "__main__":
    import tkinter as tk

    root = tk.Tk()
    root.title(app._title)
    app._root = root
    _pack_screen(app, _state.get("screen", "menu"))
    root.mainloop()
