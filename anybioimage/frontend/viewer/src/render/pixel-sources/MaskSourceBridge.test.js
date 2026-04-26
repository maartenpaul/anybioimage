/** @vitest-environment jsdom */
import { describe, it, expect, vi } from 'vitest';
import { MaskSourceBridge } from './MaskSourceBridge.js';

function fakeModel() {
  const listeners = {};
  return {
    on: (evt, cb) => { (listeners[evt] = listeners[evt] || []).push(cb); },
    off: (evt, cb) => { listeners[evt] = (listeners[evt] || []).filter((x) => x !== cb); },
    send: vi.fn(),
    _emit: (evt, content, buffers) => (listeners[evt] || []).forEach((cb) => cb(content, buffers)),
  };
}

describe('MaskSourceBridge', () => {
  it('requests a mask on subscribe when not yet cached', () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    bridge.subscribe('m1', () => {});
    expect(model.send).toHaveBeenCalledWith({ kind: 'mask_request', id: 'm1' });
  });

  it('stores bytes from a `kind:mask` message and notifies subscribers', async () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    const sub = vi.fn();
    bridge.subscribe('m1', sub);
    const pixels = new Uint8Array(4 * 2 * 2);     // 2×2 RGBA
    pixels.set([255, 0, 0, 128], 0);
    model._emit('msg:custom', { kind: 'mask', id: 'm1', width: 2, height: 2, dtype: 'uint8' },
                [pixels.buffer]);
    await Promise.resolve();
    const entry = bridge.get('m1');
    expect(entry).toBeTruthy();
    expect(entry.width).toBe(2);
    expect(entry.height).toBe(2);
    expect(entry.pixels.slice(0, 4)).toEqual(new Uint8Array([255, 0, 0, 128]));
    expect(sub).toHaveBeenCalledWith(entry);
  });

  it('multiple subscribers share a single request', () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    bridge.subscribe('m1', () => {});
    bridge.subscribe('m1', () => {});
    expect(model.send).toHaveBeenCalledTimes(1);
  });

  it('destroy detaches the listener', () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    bridge.subscribe('m1', () => {});
    bridge.destroy();
    model._emit('msg:custom', { kind: 'mask', id: 'm1', width: 1, height: 1 }, [new Uint8Array(4).buffer]);
    expect(bridge.get('m1')).toBeUndefined();
  });

  it('bakes an ImageData fallback when createImageBitmap is not available', async () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    const got = new Promise((resolve) => bridge.subscribe('m1', (e) => { if (e.bitmap) resolve(e); }));
    const pixels = new Uint8Array(4 * 1 * 1);
    model._emit('msg:custom', { kind: 'mask', id: 'm1', width: 1, height: 1, dtype: 'uint8' },
                [pixels.buffer]);
    const entry = await got;
    expect(entry.bitmap).toBeTruthy();
  });
});
