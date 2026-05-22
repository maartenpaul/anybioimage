"""Channel toggle → next paint p95 ≤ 16 ms [spec §1 perf budget].

Labels checked:
  layers:image   — per-layer rebuild time when _channel_settings flips.
  layers:build   — outer memo wall time.

This test fails BASELINE (Task 8), passes after Task 9 splits the monolithic
layers useMemo into per-layer sub-memos.
"""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 16.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
WARMUP = 10
MEASURE = 30


def _toggle_channel(widget, idx: int) -> None:
    settings = widget.get("_channel_settings") or []
    if not settings:
        return
    s = list(settings)
    s[idx] = {**s[idx], "visible": not s[idx].get("visible", True)}
    widget.set("_channel_settings", s)


@pytest.mark.integration
def test_channel_toggle_meets_budget(widget):
    widget.clear_perf()
    for _ in range(WARMUP):
        _toggle_channel(widget, 0)
        _toggle_channel(widget, 0)
    widget.clear_perf()
    for _ in range(MEASURE):
        _toggle_channel(widget, 0)
        _toggle_channel(widget, 0)

    widget._page.wait_for_timeout(300)  # settle
    p95 = widget.perf_p95("layers:image")
    assert p95 <= BUDGET_MS, f"channel toggle layers:image p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"
