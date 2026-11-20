// anybioimage/frontend/viewer/src/util/perf.test.js
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mark, measure, trace, getPerfReport, clearPerf } from './perf.js';

describe('perf.js', () => {
  beforeEach(() => {
    clearPerf();
    globalThis.window = globalThis.window || {};
    globalThis.window.__ANYBIOIMAGE_PERF = true;
  });

  afterEach(() => {
    globalThis.window.__ANYBIOIMAGE_PERF = false;
    clearPerf();
  });

  it('no-ops when the flag is off', () => {
    globalThis.window.__ANYBIOIMAGE_PERF = false;
    mark('a'); mark('b');
    measure('ab', 'a', 'b');
    expect(getPerfReport()).toEqual({});
  });

  it('records a measurement when the flag is on', () => {
    mark('start');
    // Busy-wait a hair so duration > 0.
    const t0 = performance.now();
    while (performance.now() - t0 < 1) { /* spin 1 ms */ }
    mark('end');
    measure('busy', 'start', 'end');
    const r = getPerfReport();
    expect(r.busy).toBeDefined();
    expect(r.busy.count).toBe(1);
    expect(r.busy.mean).toBeGreaterThan(0);
  });

  it('trace() wraps a sync fn and records duration', () => {
    const out = trace('op', () => 42);
    expect(out).toBe(42);
    const r = getPerfReport();
    expect(r.op.count).toBe(1);
  });

  it('trace() wraps an async fn and records duration', async () => {
    const out = await trace('async-op', async () => {
      await new Promise((r) => setTimeout(r, 2));
      return 'ok';
    });
    expect(out).toBe('ok');
    const r = getPerfReport();
    expect(r['async-op'].count).toBe(1);
    expect(r['async-op'].mean).toBeGreaterThan(0);
  });

  it('trace() records even if the wrapped fn throws', () => {
    expect(() => trace('boom', () => { throw new Error('x'); })).toThrow('x');
    const r = getPerfReport();
    expect(r.boom.count).toBe(1);
  });

  it('computes p50 / p95 / p99 over many samples', () => {
    for (let i = 1; i <= 100; i++) {
      trace('linear', () => {
        const t0 = performance.now();
        while (performance.now() - t0 < i * 0.1) { /* spin */ }
      });
    }
    const r = getPerfReport();
    expect(r.linear.count).toBe(100);
    expect(r.linear.p50).toBeLessThan(r.linear.p95);
    expect(r.linear.p95).toBeLessThan(r.linear.p99 + 0.001);
  });

  it('ring buffer retains at most 1000 entries per label', () => {
    for (let i = 0; i < 1200; i++) {
      trace('bounded', () => {});
    }
    const r = getPerfReport();
    expect(r.bounded.count).toBe(1000);
  });

  it('clearPerf() drops all records', () => {
    trace('x', () => {});
    clearPerf();
    expect(getPerfReport()).toEqual({});
  });
});
