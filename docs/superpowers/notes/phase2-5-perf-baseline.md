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

## Notes

- **Channel toggle baseline:** The `layers:image` perf label is not yet emitted
  by the frontend — it will be added as part of Task 9's monolithic-memo split.
  The test raises `KeyError: no perf samples under label 'layers:image'` and
  fails. The existing `layers:build` label shows sub-millisecond times (0.10 ms
  p95) because the current implementation does not yet measure per-layer work
  separately.

- **T/Z scrub baseline:** The p95 latencies are 646–908 ms, massively exceeding
  the 30 ms budget. The root cause is the chunk-bridge round-trip — every
  `current_t` / `current_z` change triggers a synchronous Python fetch with no
  prefetch. Task 10 (tile prefetch on settle) will address this.

- **p50 vs p95 gap on T/Z scrub:** p50 ≈ 21–22 ms is already within budget,
  showing that many requests hit warm paths. The tail (p95/p99 > 600 ms) is
  driven by cold-cache fetches where Python must serve fresh tiles over the
  websocket bridge.

- All budgets include a 1.5× multiplier on CI
  (`ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER` env var).
