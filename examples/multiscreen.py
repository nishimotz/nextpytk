"""nextpytk multi-screen sample: state-driven screen switching.

Uses ``@app.stages`` so only the stage named by ``state["screen"]`` is
visible at a time.  Buttons update state; changing ``screen`` rerenders the
body automatically.

State keys:
  - counter: int (order count)
  - items: list[str] (ordered items)
  - screen: str ("menu" | "confirm" | "thanks")
  - selected: str (current menu pick)
  - msg: str (feedback line)
"""

from nextpytk import TkApp, Layout

app = TkApp(title="Order Manager")


@app.stages(
    "order",
    stages=["menu", "confirm", "thanks"],
    key="screen",
    toplevel_widgets=("title",),
    initial_state={
        "counter": 0,
        "items": [],
        "screen": "menu",
        "selected": "",
        "msg": "",
    },
    view_layouts={
        "menu": Layout()
            .section("menu_lbl")
            .grid()
                .at(0, 0).cell("ramen", "gyoza")
                .next_row().cell("rice")
            .end_grid()
            .section("selected_lbl")
            .section("add", "confirm")
            .section("items_lbl")
            .section("result_lbl"),
        "confirm": Layout()
            .section("confirm_title")
            .section("confirm_items")
            .section("back", "submit")
            .section("reset_confirm"),
        "thanks": Layout()
            .section("thanks_title")
            .section("thanks_summary")
            .section("reset_thanks"),
    },
)
def _order_stages():
    pass


# --- Toplevel widgets ---

@app.label("title", role="heading")
def title():
    return "🍜 Order Counter"


def _do_reset(_vals=None):
    return {
        "counter": 0,
        "items": [],
        "selected": "",
        "screen": "menu",
        "msg": "Reset",
    }


# --- Menu widgets ---

with app.view("menu") as v:
    @v.label("menu_lbl")
    def menu_lbl():
        return f"Menu: order {app.state['counter']}"

    @v.status("selected_lbl")
    def selected_lbl():
        sel = app.state.get("selected", "")
        return f"Selected: {sel}" if sel else "Select a menu item"

    @v.label("items_lbl")
    def items_lbl():
        lst = app.state.get("items", [])
        if not lst:
            return "Order history: (none)"
        return "Order history:\n" + "\n".join(
            f"  {i+1}. {x}" for i, x in enumerate(lst)
        )

    @v.label("result_lbl")
    def result_lbl():
        return app.state.get("msg", "")

    @v.button("ramen", label="🍜 Ramen")
    def on_ramen(vals):
        return {"selected": "ramen", "msg": "Ramen selected"}

    @v.button("gyoza", label="🥟 Gyoza")
    def on_gyoza(vals):
        return {"selected": "gyoza", "msg": "Gyoza selected"}

    @v.button("rice", label="🍚 Rice")
    def on_rice(vals):
        return {"selected": "rice", "msg": "Rice selected"}

    @v.button("add", label="✅ Add")
    def on_add(vals):
        sel = app.state.get("selected", "")
        if not sel:
            return {"msg": "Please select a menu item first"}
        items = list(app.state.get("items", []))
        items.append(sel)
        cnt = app.state.get("counter", 0) + 1
        return {
            "items": items,
            "counter": cnt,
            "msg": f"Added {sel} (total {cnt} items)",
            "selected": "",
        }

    @v.button("confirm", label="📋 Confirm order")
    def on_confirm(vals):
        items = app.state.get("items", [])
        if not items:
            return {"msg": "No order"}
        return {"screen": "confirm", "msg": ""}


# --- Confirm widgets ---

with app.view("confirm") as v:
    @v.label("confirm_title", role="heading")
    def confirm_title():
        return "📋 Confirm order"

    @v.label("confirm_items")
    def confirm_items():
        lst = app.state.get("items", [])
        if not lst:
            return "(no order)"
        return "\n".join(f"  {i+1}. {x}" for i, x in enumerate(lst))

    @v.button("back", label="← Back to menu")
    def on_back(vals):
        return {"screen": "menu", "msg": ""}

    @v.button("submit", label="👍 Place order")
    def on_submit(vals):
        cnt = app.state.get("counter", 0)
        return {"screen": "thanks", "msg": f"Thank you! Order for {cnt} items confirmed"}

    @v.button("reset_confirm", label="🔄 Start over")
    def on_reset_confirm(vals):
        return _do_reset(vals)


# --- Thanks widgets ---

with app.view("thanks") as v:
    @v.label("thanks_title", role="heading")
    def thanks_title():
        return "✅ Thank you for your order!"

    @v.label("thanks_summary")
    def thanks_summary():
        cnt = app.state.get("counter", 0)
        lst = app.state.get("items", [])
        return f"We received your order for {cnt} items.\nDetails:\n" + "\n".join(
            f"  {i+1}. {x}" for i, x in enumerate(lst)
        )

    @v.button("reset_thanks", label="🔄 Start over")
    def on_reset_thanks(vals):
        return _do_reset(vals)


if __name__ == "__main__":
    app.run(stages="order")
