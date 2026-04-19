import { describe, it, expect, vi } from 'vitest';
import { AnywidgetPixelSource } from './anywidget-source.js';

function mockModel(onSend) {
  const listeners = {};
  return {
    send: onSend,
    on: (name, cb) => { listeners[name] = cb; },
    off: () => {},
    emit: (name, content, buffers) => { if (listeners[name]) listeners[name](content, buffers); },
  };
}

describe('AnywidgetPixelSource', () => {
  it('resolves getTile with Viv-shaped output', async () => {
    const raw = new Uint16Array([1, 2, 3, 4]).buffer;
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 2, h: 2, dtype: 'uint16' },
        [raw]));
    });
    const src = new AnywidgetPixelSource(model, {
      shape: { t: 1, c: 1, z: 1, y: 2, x: 2 },
      dtype: 'Uint16',
      tileSize: 512,
    });
    const out = await src.getTile({
      x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    });
    expect(out.width).toBe(2);
    expect(out.height).toBe(2);
    expect(out.data).toBeInstanceOf(Uint16Array);
    expect(Array.from(out.data)).toEqual([1, 2, 3, 4]);
  });

  it('rejects getTile on abort', async () => {
    const model = mockModel(() => {}); // never replies
    const src = new AnywidgetPixelSource(model, {
      shape: { t: 1, c: 1, z: 1, y: 2, x: 2 },
      dtype: 'Uint16',
      tileSize: 512,
    });
    const ac = new AbortController();
    const p = src.getTile({ x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: ac.signal });
    ac.abort();
    await expect(p).rejects.toThrow(/abort/i);
  });

  it('surfaces server errors', async () => {
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: false, error: 'out of bounds' }, []));
    });
    const src = new AnywidgetPixelSource(model, {
      shape: { t: 1, c: 1, z: 1, y: 2, x: 2 },
      dtype: 'Uint16',
      tileSize: 512,
    });
    await expect(src.getTile({
      x: 9, y: 9, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    })).rejects.toThrow(/out of bounds/);
  });
});
