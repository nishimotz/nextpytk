"""nextpytk disk usage flat viewer — async version.

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
from typing import Any

from nextpytk import TkApp, Layout
from nextpytk.types import EventSeq, Fill, SelectMode

app = TkApp(title="nextpytk Disk Usage (async)")


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
        return [], 0, 0, f"Read failed: {exc}"

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
        return [], 0, 0, f"Scan failed: {exc}"

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
        return "Scanning…"
    if _error:
        return _error
    return "Idle — Up / BackSpace, Return on a directory"


@app.status("summary_lbl", description="entry count and total bytes")
def summary_lbl():
    return "—"


@app.status("detail_lbl", description="selected entry details")
def detail_lbl():
    return "(select a row)"


@app.listbox(
    "file_list",
    selectmode=SelectMode.BROWSE,
    enabled_if=lambda vals: not _busy,
    events={
        EventSeq.RETURN: lambda _s: _navigate_child(),
        EventSeq.PRIMARY_DOUBLE_CLICK: lambda _s: _navigate_child(),
        EventSeq.BACKSPACE: lambda _s: _navigate_parent(),
    },
)
def on_file_list_select(idx: int) -> dict[str, str]:
    if idx < 0 or idx >= len(_lines):
        return {"detail_lbl": "(select a row)"}
    p, is_dir, sz = _lines[idx]
    kind = "Directory" if is_dir else "File"
    szs = human_bytes(sz) if sz >= 0 else "?"
    return {"detail_lbl": f"{kind}: {p} · {szs}"}


@app.button("up_btn", label="Up (BackSpace)", primary=True)
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
        the_app.sync()
        return

    _busy = False  # before touching the list: enabled_if gates updates
    w.delete(0, "end")
    _lines.clear()

    cur = cwd()
    lines, total_bytes, n, err = outcome
    if err:
        _error = err
        the_app.apply_state({
            "path_lbl": str(cur),
            "summary_lbl": "—",
            "detail_lbl": err,
            "status_lbl": err,
        })
        the_app.sync()
        return

    _error = ""
    for p, is_dir, sz in lines:
        _lines.append((p, is_dir, sz))
        mark = "/" if is_dir else ""
        w.insert("end", f"{human_bytes(sz) if sz >= 0 else '?'}\t{p.name}{mark}")

    detail = "(select a row)"
    if w.size() > 0:
        w.selection_clear(0)
        w.selection_set(0)
        w.activate(0)
        w.see(0)
        # Programmatic selection doesn't fire <<ListboxSelect>>, so update manually.
        detail = on_file_list_select(0).get("detail_lbl", detail)

    the_app.apply_state({
        "path_lbl": str(cur),
        "summary_lbl": f"{n} entries · displayed total {human_bytes(total_bytes)}",
        "status_lbl": "Idle — Up / BackSpace, Return on a directory",
        "detail_lbl": detail,
    })
    the_app.sync()


async def _refresh_async(the_app: TkApp, target: Path) -> None:
    """Non-blocking scan: set busy state, scan in thread, apply result."""
    global _busy
    _busy = True
    the_app.apply_state({
        "path_lbl": str(target),
        "status_lbl": "Scanning…",
        "detail_lbl": "Scanning in the background…",
    })
    the_app.sync()
    try:
        outcome = await asyncio.to_thread(scan_directory, target)
    except Exception as exc:
        outcome = ([], 0, 0, f"Error: {exc}")
    try:
        _apply_scan_result(the_app, outcome)
    except Exception as exc:
        _busy = False
        the_app.apply_state({
            "status_lbl": f"Error: {exc}",
            "detail_lbl": str(exc),
        })
        the_app.sync()


def _refresh(the_app: TkApp, target: Path) -> None:
    """Sync refresh for initial load. Blocks GUI."""
    global _busy
    _busy = True
    try:
        outcome = scan_directory(target)
        _apply_scan_result(the_app, outcome)
    except Exception as exc:
        _busy = False
        the_app.apply_state({
            "status_lbl": f"Error: {exc}",
            "detail_lbl": str(exc),
        })
        the_app.sync()


def _navigate_parent() -> dict[str, Any]:
    global _error
    if _busy:
        return {}
    cur = cwd()
    parent = cur.parent
    if parent == cur:
        app.apply_state({"status_lbl": "Root directory"})
        return {}
    if len(_stack) > 1:
        _stack.pop()
    else:
        _stack[0] = parent.resolve()
    _error = ""
    app.spawn(_refresh_async(app, _stack[-1]))
    return {}


def _navigate_child() -> dict[str, Any]:
    global _error
    if _busy:
        return {}
    w = app.widget("file_list")
    if w is None or not isinstance(w, tk.Listbox):
        return {}
    try:
        sel = w.curselection()
        if not sel:
            return {}
        i = int(sel[0])
        p, is_dir, _ = _lines[i]
        if is_dir and p.is_dir():
            _stack.append(p.resolve())
            _error = ""
            app.spawn(_refresh_async(app, _stack[-1]))
    except (ValueError, IndexError):
        pass
    return {}


def _on_ready(the_app: TkApp) -> None:
    """Do initial sync scan."""
    _refresh(the_app, _stack[-1])


if __name__ == "__main__":
    app.run_async(
        layout=(
            Layout()
            .section("up_btn", side="bottom")
            .section("path_lbl")
            .section("status_lbl")
            .section("summary_lbl")
            .section("detail_lbl")
            .section("file_list", fill=Fill.BOTH, expand=True)
        ),
        on_ready=_on_ready,
        geometry="620x800",
    )
