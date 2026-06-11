// anybioimage/frontend/viewer/src/util/perf.js
/**
 * Perf instrumentation — always compiled, no-op unless window.__ANYBIOIMAGE_PERF is true.
 *
 * API (spec §3):
 *   mark(name)              — records a timestamp keyed by name.
 *   measure(label, a, b)    — records duration (in ms) between marks a and b under label.
 *   trace(label, fn)        — wraps a sync or async fn; records its wall-clock duration.
 *   getPerfReport()         — { [label]: { count, mean, p50, p95, p99 } }
 *   clearPerf()             — drops all recorded data.
 *
 * Storage: per-label ring buffer of the last 1000 durations.
 * Ordering: percentiles are sorted-copy of the ring at report-time, so mark/measure calls stay O(1).
 */

const MAX_SAMPLES = 1000;
const _marks = new Map();       // name → timestamp (ms)
const _rings = new Map();       // label → number[] (ring buffer of durations ms)

function enabled() {
  return typeof window !== 'undefined' && window.__ANYBIOIMAGE_PERF === true;
}

function now() {
  return (typeof performance !== 'undefined' && performance.now)
    ? performance.now()
    : Date.now();
}

function push(label, duration) {
  let ring = _rings.get(label);
  if (!ring) { ring = []; _rings.set(label, ring); }
  ring.push(duration);
  if (ring.length > MAX_SAMPLES) ring.splice(0, ring.length - MAX_SAMPLES);
}

export function mark(name) {
  if (!enabled()) return;
  _marks.set(name, now());
}

export function measure(label, startMark, endMark) {
  if (!enabled()) return;
  const a = _marks.get(startMark);
  const b = _marks.get(endMark);
  if (a == null || b == null) return;
  push(label, b - a);
}

export function trace(label, fn) {
  if (!enabled()) return fn();
  const t0 = now();
  let out;
  try {
    out = fn();
  } catch (err) {
    push(label, now() - t0);
    throw err;
  }
  if (out && typeof out.then === 'function') {
    return out.then(
      (val) => { push(label, now() - t0); return val; },
      (err) => { push(label, now() - t0); throw err; },
    );
  }
  push(label, now() - t0);
  return out;
}

function percentile(sorted, p) {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * p));
  return sorted[idx];
}

export function getPerfReport() {
  const out = {};
  for (const [label, ring] of _rings.entries()) {
    if (ring.length === 0) continue;
    const sorted = ring.slice().sort((a, b) => a - b);
    let sum = 0;
    for (const v of sorted) sum += v;
    out[label] = {
      count: sorted.length,
      mean: sum / sorted.length,
      p50: percentile(sorted, 0.50),
      p95: percentile(sorted, 0.95),
      p99: percentile(sorted, 0.99),
    };
  }
  return out;
}

export function clearPerf() {
  _marks.clear();
  _rings.clear();
}
