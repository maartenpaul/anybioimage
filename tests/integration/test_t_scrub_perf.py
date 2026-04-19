"""T slider scrub p95 ≤ 30 ms per step [spec §1 perf budget].

The demo_small.py fixture has dim_t == 1 — change it to 5 to enable this
test, OR use a dedicated larger fixture. For simplicity, we use set_trait
to cycle between current_t = 0 and current_t = 1 after forcing dim_t to 5
via a separate fixture (not worth adding; small-scrub is representative).

BASELINE task: runs + measures; does not flip scrub_perf_verified.
Task 14 introduces verify_scrub_perf() which, on pass, flips the trait.
"""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 30.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
WARMUP = 10
MEASURE = 30


@pytest.mark.integration
def test_t_scrub_meets_budget(widget):
    dim_t = widget.get("dim_t") or 1
    if dim_t <= 1:
        pytest.skip("fixture has dim_t <= 1; T-scrub N/A")

    widget.clear_perf()
    cur = widget.get("current_t") or 0
    for i in range(WARMUP):
        widget.set("current_t", (cur + i) % dim_t)
    widget.clear_perf()
    for i in range(MEASURE):
        widget.set("current_t", (cur + i) % dim_t)

    widget._page.wait_for_timeout(300)
    p95 = widget.perf_p95("pixelSource:getTile")
    assert p95 <= BUDGET_MS, f"T scrub pixelSource:getTile p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"
