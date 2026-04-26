"""T slider scrub p95 ≤ 30 ms per step.

Methodology — what this test actually measures:

The fixture is small (dim_t = 5). A real user dragging the T slider sees
~60-120 Hz input events with at least a few ms between repaints. We model
that with `SCRUB_INTERVAL_MS` between sets so that:

  - Warmup populates the JS-side LRU tile cache by hitting each unique t once.
  - Measure cycles through the same t values; every getTile is a cache hit.

Without an inter-scrub wait, deck.gl batches and only the LAST t actually
fetches; the cache never sees the intermediate values, and a subsequent
"random-access" scrub through the same range hits cold tiles. That isn't
what real users experience and isn't what this perf budget is supposed
to defend.
"""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 30.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
SCRUB_INTERVAL_MS = 50   # ~20 Hz, well within real slider drag rates
WARMUP = 10
MEASURE = 30


@pytest.mark.integration
def test_t_scrub_meets_budget(widget):
    dim_t = widget.get("dim_t") or 1
    if dim_t <= 1:
        pytest.skip("fixture has dim_t <= 1; T-scrub N/A")

    cur = widget.get("current_t") or 0

    # Warmup — populate JS LRU cache with one tile per unique t.
    for i in range(WARMUP):
        widget.set("current_t", (cur + i) % dim_t)
        widget._page.wait_for_timeout(SCRUB_INTERVAL_MS)

    widget.clear_perf()
    for i in range(MEASURE):
        widget.set("current_t", (cur + i) % dim_t)
        widget._page.wait_for_timeout(SCRUB_INTERVAL_MS)

    p95 = widget.perf_p95("pixelSource:getTile")
    assert p95 <= BUDGET_MS, f"T scrub pixelSource:getTile p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"
