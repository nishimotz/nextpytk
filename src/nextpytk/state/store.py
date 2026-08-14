"""StateStore: reactive state storage, write tracing, and state validation."""

from __future__ import annotations

import tkinter as tk
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nextpytk.widgets import WidgetSpec


def levenshtein(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


class StateStore:
    """Encapsulates reactive state dict, Tk variables, write trace ingestion, and validation."""

    def __init__(self, *, ingest_trace: bool = False, debug: bool = False) -> None:
        self.state: dict[str, Any] = {}
        self.tk_vars: dict[str, tk.Variable] = {}
        self.syncing_var_keys: set[str] = set()
        self.pending_ingest: set[str] = set()
        self.ingest_flush_job: str | None = None
        self.ingest_trace: bool = ingest_trace
        self.debug: bool = debug
        self.building: bool = False

    def reset(self) -> None:
        """Reset state tracking data structures."""
        self.pending_ingest.clear()
        self.ingest_flush_job = None
        self.syncing_var_keys.clear()

    def warn_unknown_keys(
        self,
        update: dict[str, Any],
        *,
        known_keys: set[str],
    ) -> None:
        """Warn or error when update contains keys that do not match known widgets/state."""
        all_known = known_keys | set(self.state.keys()) | set(self.tk_vars.keys())
        suspects: list[str] = []
        for k in update:
            if k in all_known:
                continue
            suspects.append(k)
            candidates = [
                cand for cand in sorted(all_known)
                if abs(len(cand) - len(k)) <= 2 and levenshtein(k, cand) <= 2
            ]
            if candidates:
                hint = f" (did you mean '{candidates[0]}' ?)"
            else:
                hint = ""
            warnings.warn(
                f"apply_state: unknown state key '{k}'{hint}",
                UserWarning,
                stacklevel=4,
            )
        if suspects and self.debug:
            raise KeyError(f"unknown state key(s): {suspects}")

    def register_var(
        self,
        key: str,
        var: tk.Variable,
        *,
        on_ingest: Callable[[str], None],
    ) -> None:
        """Register a Tcl variable under *key*, installing an ingest trace if enabled."""
        self.tk_vars[key] = var
        if self.ingest_trace:
            try:
                var.trace_add(
                    "write",
                    lambda _n, _i, _op, k=key: on_ingest(k),
                )
            except tk.TclError:
                pass

    def on_var_ingest(
        self,
        key: str,
        root: tk.Misc | None,
        flush_callback: Callable[[], None],
    ) -> None:
        """Trace callback: a user edit changed ``var``; queue it for ingest."""
        if key in self.syncing_var_keys or self.building:
            return
        self.pending_ingest.add(key)
        if root is None:
            return
        if self.ingest_flush_job is None:
            try:
                self.ingest_flush_job = root.after_idle(flush_callback)
            except tk.TclError:
                self.ingest_flush_job = None
