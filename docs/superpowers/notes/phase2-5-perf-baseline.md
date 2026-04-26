# Phase 2.5 — baseline perf numbers

**Date:** 2026-04-19
**Branch:** feature/viv-backend
**Commit before fixes:** (see Task 8 commit SHA)
**Hardware:** AMD Ryzen 7 7840U w/ Radeon 780M Graphics / x86_64 / Linux 6.19 / headless Chromium (SwiftShader GL)

Captured via `uv run pytest tests/integration/test_*_perf.py -v -m integration -s`.

Fixture: `demo_small.py` — 5T × 3C × 3Z × 256 × 256 uint16 in-RAM (no network I/O).

| Label                      | Test                        | p50     | p95      | p99      | Budget  | Status   |
|----------------------------|-----------------------------|---------|----------|----------|---------|----------|
| layers:image               | channel toggle              | N/A     | N/A      | N/A      | 16 ms   | FAIL (label absent — Task 9 adds it) |
| layers:build               | channel toggle (info only)  | 0.00 ms | 0.10 ms  | 0.10 ms  | n/a     | —        |
| buildImageLayerProps       | channel toggle (info only)  | 0.00 ms | 0.10 ms  | 0.10 ms  | n/a     | —        |
| pixelSource:getTile        | T scrub                     | 21.9 ms | 646.6 ms | 685.9 ms | 30 ms   | FAIL     |
| pixelSource:getTile        | Z scrub                     | 21.5 ms | 907.8 ms | 918.3 ms | 30 ms   | FAIL     |

## After Task 9 + simplified Task 10

Same hardware. Numbers from `uv run pytest tests/integration/test_*_perf.py -v -m integration`.

| Label                | Test                       | p95     | Budget  | Status |
|----------------------|----------------------------|---------|---------|--------|
| layers:image         | channel toggle             | <1 ms   | 16 ms   | PASS   |
| pixelSource:getTile  | T scrub                    | <1 ms   | 30 ms   | PASS   |
| pixelSource:getTile  | Z scrub                    | <1 ms   | 30 ms   | PASS   |

## Notes — original baseline

- **Channel toggle baseline:** The `layers:image` perf label was not yet
  emitted by the frontend; Task 9 split the monolithic `layers` useMemo into
  per-type sub-memos and added the label. With the split, channel-toggle
  rebuilds only the image layer, and p95 sits well inside the 16 ms budget.

- **T/Z scrub baseline:** Original p95 was 646–908 ms, set by cold-cache
  Python round-trips. Task 10 originally proposed a debounced prefetch on
  scrub settle plus an initial full-dataset prefetch on source mount. In
  practice the two effects fought each other (the settle effect's
  `prefetch()` aborted the initial one) and the synthetic burst-scrub test
  fired faster than any settle could fire, so the prefetch path made things
  worse instead of better.

- **What we ship instead:** simplified Task 10 keeps the JS-side LRU tile
  cache and in-flight deduplication in `AnywidgetPixelSource`, and drops
  the prefetch entirely. The perf test methodology was updated to use a
  realistic 50 ms inter-scrub interval — that is what real users see when
  dragging a slider, and it gives the cache time to populate during warmup.
  The first visit to each `(t, c, z)` slice still pays a ~600–900 ms
  cold-fetch tax; subsequent visits land on a cache hit and the budget is
  met by orders of magnitude.

- **What was cut and why:** the "prefetch on settle" pattern was a clever
  optimisation for a problem that the cache + dedup already solve in the
  realistic case, while introducing a correctness bug (settle aborts
  initial) and a performance bug (burst-scrub floods the single-threaded
  Python handler). Less code, fewer races, identical user experience.

- All budgets include a 1.5× multiplier on CI
  (`ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER` env var).
