"""tkouter disk usage flat viewer — async version.

ncdu-inspired flat list of disk usage per entry.
- ``app.run_async()`` with asyncio event loop (Tk + asyncio cooperative scheduling)
- ``app.spawn()`` for non-blocking directory scan
- GUI stays responsive during scan (status updates, button guard)
"""

from __future__ import annotations

import asyncio
import os
import tkinter as tk
from pathlib import Path

from tkouter import TkApp, Layout

app = TkApp(title="tkouter 使用量 (async)")


# ─── helpers ───

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


# ─── blocking scan (runs in asyncio.to_thread) ───

def scan_directory(cur: Path) -> tuple[list[tuple[Path, bool, int]], int, int, str]:
    try:
        with os.scandir(cur) as it:
            entries = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError as exc:
        return [], 0, 0, f"読み取り失敗: {exc}"

    rows: list[tuple[str, Path, bool]] = []
    for e in entries:
        p = Path(e.path)
        rows.append((e.name, p, e.is_dir(follow_symlinks=False)))

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
_busy: bool = False
_error: str = ""


def cwd() -> Path:
    return _stack[-1]


def _short_path(p: Path, max_len: int = 60) -> str:
    s = str(p)
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1):]


# ─── widget registrations ───

@app.status("path_lbl", description="current directory path")
def path_lbl():
    return _short_path(cwd())


@app.status("status_lbl", description="status message")
def status_lbl():
    if _busy:
        return "スキャン中…"
    if _error:
        return _error
    return "待機中 — 親へ / BackSpace、ディレクトリで Return"


@app.status("summary_lbl", description="entry count and total bytes")
def summary_lbl():
    return "—"


@app.status("detail_lbl", description="selected entry details")
def detail_lbl():
    return "（行を選択）"


@app.listbox("file_list", height=18, selectmode="browse", enabled_if=lambda vals: not _busy)
def on_file_list_select(value: str) -> dict[str, str]:
    if not value:
        return {}
    for p, is_dir, sz in _lines:
        if p.name == value:
            kind = "ディレクトリ" if is_dir else "ファイル"
            szs = human_bytes(sz) if sz >= 0 else "?"
            return {"detail_lbl": f"{kind}: {p} · {szs}"}
    return {}


@app.button("up_btn", label="親へ (BackSpace)", enabled_if=lambda vals: not _busy)
def on_up(vals: dict) -> dict[str, str]:
    _navigate_parent()
    return {}


# ─── core logic ───

def _apply_scan_result(
    the_app: TkApp,
    outcome: tuple[list[tuple[Path, bool, int]], int, int, str],
) -> None:
    """Called on main thread after background scan completes."""
    global _lines, _busy, _error
    w = the_app.widget("file_list")
    if w is None or not isinstance(w, tk.Listbox):
        _busy = False
        return

    w.delete(0, "end")
    _lines.clear()

    cur = cwd()
    lines, total_bytes, n, err = outcome
    if err:
        _busy = False
        _error = err
        the_app.apply_state({
            "path_lbl": str(cur),
            "summary_lbl": "—",
            "detail_lbl": err,
            "status_lbl": err,
        })
        return

    _error = ""
    for p, is_dir, sz in lines:
        _lines.append((p, is_dir, sz))
        mark = "/" if is_dir else ""
        w.insert("end", f"{human_bytes(sz) if sz >= 0 else '?'}\t{p.name}{mark}")

    if w.size() > 0:
        w.selection_clear(0)
        w.selection_set(0)
        w.activate(0)
        w.see(0)

    _busy = False
    the_app.apply_state({
        "path_lbl": str(cur),
        "summary_lbl": f"エントリ {n} 件 · 表示の合計 {human_bytes(total_bytes)}",
        "status_lbl": "待機中 — 親へ / BackSpace、ディレクトリで Return",
    })
    the_app.sync()


async def _refresh_async(the_app: TkApp, target: Path) -> None:
    """Non-blocking scan: set busy state, scan in thread, apply result."""
    global _busy
    _busy = True
    the_app.apply_state({
        "path_lbl": str(target),
        "status_lbl": "スキャン中…",
        "detail_lbl": "バックグラウンドで走査中…",
    })
    the_app.sync()
    try:
        outcome = await asyncio.to_thread(scan_directory, target)
    except Exception as exc:
        outcome = ([], 0, 0, f"エラー: {exc}")
    _apply_scan_result(the_app, outcome)


def _refresh(the_app: TkApp, target: Path) -> None:
    """Sync refresh for initial load. Blocks GUI."""
    global _busy
    _busy = True
    outcome = scan_directory(target)
    _apply_scan_result(the_app, outcome)


def _navigate_parent() -> None:
    global _error
    if _busy:
        return
    cur = cwd()
    parent = cur.parent
    if parent == cur:
        app.apply_state({"status_lbl": "ルートディレクトリです"})
        return
    if len(_stack) > 1:
        _stack.pop()
    else:
        _stack[0] = parent.resolve()
    _error = ""
    app.spawn(_refresh_async(app, _stack[-1]))


def _navigate_child() -> None:
    global _error
    if _busy:
        return
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
            _error = ""
            app.spawn(_refresh_async(app, _stack[-1]))
    except (ValueError, IndexError):
        return


def _on_ready(the_app: TkApp) -> None:
    """Wire key bindings and do initial sync scan."""
    lb = the_app.widget("file_list")
    if lb is not None and isinstance(lb, tk.Listbox):
        lb.bind("<Return>", lambda _e: _navigate_child())
        lb.bind("<BackSpace>", lambda _e: _navigate_parent())
    _refresh(the_app, _stack[-1])


if __name__ == "__main__":
    app.run_async(
        layout=(
            Layout()
            .section("path_lbl")
            .section("status_lbl")
            .section("summary_lbl")
            .section("detail_lbl")
            .section("file_list", fill="both", expand=True)
            .section("up_btn")
        ),
        on_ready=_on_ready,
        geometry="620x520",
    )
