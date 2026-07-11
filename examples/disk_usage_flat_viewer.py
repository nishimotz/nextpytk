"""nextpytk disk usage flat viewer — synchronous directory scanner.

ncdu-inspired flat list of disk usage per entry.
- Listbox with name + du-style recursive size
- Detail line for selected entry
- Summary line (total entries / bytes)
- Parent directory navigation (button + BackSpace key)
- Child directory navigation (double-click / Return key)

*** WARNING: synchronous blocking ***
``scan_directory()`` runs on the main thread. For large directories (>10,000 files)
the GUI freezes during scanning. The async (asyncio + to_thread) version is
planned — see ROADMAP.md.
"""

from __future__ import annotations

import os
import tkinter as tk
from collections import OrderedDict
from pathlib import Path

from nextpytk import TkApp, Layout

app = TkApp(title="nextpytk 使用量 (flat)")


# ─── helper: human-readable bytes ───

def human_bytes(n: int) -> str:
    if n < 0:
        return "?"
    x = float(n)
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB"):
        if x < 1024.0 or suffix == "TiB":
            if suffix == "B":
                return f"{int(n)} B"
            return f"{x:.2f} {suffix}"
        x /= 1024.0
    return f"{int(n)} B"


# ─── du-style recursive scan ───

_DU_CACHE_MAX = 50_000


def scan_directory(cur: Path) -> tuple[list[tuple[Path, bool, int]], int, int, str]:
    """Blocking scan. Returns (lines, total_bytes, count, error_message)."""
    try:
        with os.scandir(cur) as it:
            entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError as exc:
        return [], 0, 0, f"読み取り失敗: {exc}"

    rows: list[tuple[str, Path, bool]] = []
    for e in entries:
        p = Path(e.path)
        is_dir = e.is_dir(follow_symlinks=False)
        rows.append((e.name, p, is_dir))

    bucket: dict[str, int] = {name: 0 for name, _, _ in rows}
    cur_abs = os.path.abspath(cur)

    try:
        for root, _dirs, files in os.walk(cur, followlinks=False):
            root_p = Path(root)
            for fn in files:
                fp = root_p / fn
                try:
                    sz = fp.stat().st_size
                except OSError:
                    continue
                fp_abs = os.path.abspath(fp)
                try:
                    rel = os.path.relpath(fp_abs, cur_abs)
                except ValueError:
                    continue
                if rel.startswith(".."):
                    continue
                head = Path(rel).parts[0]
                if head in bucket:
                    bucket[head] += sz
    except OSError as exc:
        return [], 0, 0, f"走査失敗: {exc}"

    lines: list[tuple[Path, bool, int]] = []
    total_bytes = 0
    for name, p, is_dir in rows:
        sz = bucket.get(name, 0)
        lines.append((p, is_dir, sz))
        if sz >= 0:
            total_bytes += sz
    return lines, total_bytes, len(rows), ""


# ─── state ───

_stack: list[Path] = [Path.cwd().resolve()]
_lines: list[tuple[Path, bool, int]] = []
_error_message: str = ""


def cwd() -> Path:
    return _stack[-1]


# ─── widget registrations ───

@app.status("path_lbl", description="current directory path")
def path_lbl():
    return str(cwd())


@app.status("status_lbl", description="status message")
def status_lbl():
    return "待機中 — 親へ / BackSpace、ディレクトリで Return"


@app.status("summary_lbl", description="entry count and total bytes")
def summary_lbl():
    return "—"


@app.status("detail_lbl", description="selected entry details")
def detail_lbl():
    return "（行を選択）"


@app.listbox("file_list", height=18, selectmode="browse")
def on_file_list_select(value):
    if not value:
        return {"detail_lbl": "（行を選択）"}
    # value は表示文字列 "サイズ\t名前[/]" — 名前部分だけ取り出す
    name = value.split("\t", 1)[-1].rstrip("/")
    for p, is_dir, sz in _lines:
        if p.name == name:
            kind = "ディレクトリ" if is_dir else "ファイル"
            szs = human_bytes(sz) if sz >= 0 else "?"
            return {"detail_lbl": f"{kind}: {p} · {szs}"}
    return {}


@app.button("up_btn", label="親へ (BackSpace)")
def on_up(vals):
    _go_parent()
    return {}


# ─── file list management ───

def _populate_file_list() -> None:
    """Repopulate listbox and state labels after a scan."""
    global _error_message
    w = app.widget("file_list")
    if w is None or not isinstance(w, tk.Listbox):
        return
    w.delete(0, "end")
    _lines.clear()

    cur = cwd()
    lines, total_bytes, n, err = scan_directory(cur)
    if err:
        _error_message = err
        app.apply_state({
            "path_lbl": str(cur),
            "summary_lbl": "—",
            "detail_lbl": err,
            "status_lbl": "スキャン失敗",
        })
        return

    _error_message = ""
    for p, is_dir, sz in lines:
        _lines.append((p, is_dir, sz))
        mark = "/" if is_dir else ""
        disp = human_bytes(sz) if sz >= 0 else "?"
        w.insert("end", f"{disp}\t{p.name}{mark}")

    if w.size() > 0:
        w.selection_clear(0)
        w.selection_set(0)
        w.activate(0)
        w.see(0)

    app.apply_state({
        "path_lbl": str(cur),
        "summary_lbl": (
            f"エントリ {n} 件 · 表示の合計 {human_bytes(total_bytes)}"
        ),
        "status_lbl": "待機中 — 親へ / BackSpace、ディレクトリで Return",
    })

    # Trigger detail update for first item (programmatic selection does not
    # fire <<ListboxSelect>>, and the returned state dict must be applied)
    first = w.get(0) if w.size() > 0 else ""
    app.apply_state(on_file_list_select(first))


def _go_parent() -> None:
    """Navigate to parent directory."""
    cur = cwd()
    parent = cur.parent
    if parent == cur:
        app.apply_state({"status_lbl": "ルートディレクトリです"})
        return
    if len(_stack) > 1:
        _stack.pop()
    else:
        _stack[0] = parent.resolve()
    _populate_file_list()


def _go_child() -> None:
    """Navigate into selected directory."""
    w = app.widget("file_list")
    if w is None or not isinstance(w, tk.Listbox):
        return
    try:
        sel = w.curselection()
        if not sel:
            return
        i = int(sel[0])
        p, is_dir, _ = _lines[i]
        if is_dir and p.is_dir():
            _stack.append(p.resolve())
            _populate_file_list()
    except (ValueError, IndexError):
        return


def _on_ready(the_app: TkApp) -> None:
    """Called after widget building. Populate listbox and wire key bindings."""
    lb = the_app.widget("file_list")
    if lb is not None and isinstance(lb, tk.Listbox):
        lb.bind("<Return>", lambda _e: _go_child())
        lb.bind("<BackSpace>", lambda _e: _go_parent())
    _populate_file_list()


if __name__ == "__main__":
    app.run(
        layout=Layout()
        .section("path_lbl")
        .section("status_lbl")
        .section("summary_lbl")
        .section("detail_lbl")
        .section("file_list", fill="both", expand=True)
        .section("up_btn"),
        on_ready=_on_ready,
    )
