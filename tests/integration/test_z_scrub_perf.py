"""Z slider scrub p95 ≤ 30 ms per step.

See test_t_scrub_perf.py for the methodology rationale (inter-scrub wait
is required so the JS-side LRU cache populates during warmup).
"""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 30.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
SCRUB_INTERVAL_MS = 50
WARMUP = 10
MEASURE = 30


@pytest.mark.integration
def test_z_scrub_meets_budget(widget):
    dim_z = widget.get("dim_z") or 1
    if dim_z <= 1:
        pytest.skip("fixture has dim_z <= 1; Z-scrub N/A")

    cur = widget.get("current_z") or 0

    for i in range(WARMUP):
        widget.set("current_z", (cur + i) % dim_z)
        widget._page.wait_for_timeout(SCRUB_INTERVAL_MS)

    widget.clear_perf()
    for i in range(MEASURE):
        widget.set("current_z", (cur + i) % dim_z)
        widget._page.wait_for_timeout(SCRUB_INTERVAL_MS)

    p95 = widget.perf_p95("pixelSource:getTile")
    assert p95 <= BUDGET_MS, f"Z scrub pixelSource:getTile p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"
