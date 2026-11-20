import { describe, it, expect } from 'vitest';
import { AnywidgetPixelSource } from './anywidget-source.js';

function mockModel(onSend) {
  const listeners = {};
  const model = {
    sendCount: 0,
    send: (msg) => { model.sendCount += 1; if (onSend) onSend(msg); },
    on: (name, cb) => { listeners[name] = cb; },
    off: () => {},
    emit: (name, content, buffers) => { if (listeners[name]) listeners[name](content, buffers); },
  };
  return model;
}

const SHAPE = [1, 1, 1, 2, 2];

describe('AnywidgetPixelSource', () => {
  it('resolves getTile with Viv-shaped output', async () => {
    const raw = new Uint16Array([1, 2, 3, 4]).buffer;
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 2, h: 2, dtype: 'uint16' },
        [raw]));
    });
    const src = new AnywidgetPixelSource(model, { shape: SHAPE, dtype: 'Uint16', tileSize: 512 });
    const out = await src.getTile({
      x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    });
    expect(out.width).toBe(2);
    expect(out.height).toBe(2);
    expect(out.data).toBeInstanceOf(Uint16Array);
    expect(Array.from(out.data)).toEqual([1, 2, 3, 4]);
  });

  it('rejects getTile on abort', async () => {
    const model = mockModel(() => {});
    const src = new AnywidgetPixelSource(model, { shape: SHAPE, dtype: 'Uint16', tileSize: 512 });
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
    const src = new AnywidgetPixelSource(model, { shape: SHAPE, dtype: 'Uint16', tileSize: 512 });
    await expect(src.getTile({
      x: 9, y: 9, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    })).rejects.toThrow(/out of bounds/);
  });

  it('exposes shape as array', () => {
    const src = new AnywidgetPixelSource(
      mockModel(() => {}),
      { shape: [2, 3, 4, 512, 512], dtype: 'Uint16', tileSize: 512 },
    );
    expect(src.shape).toEqual([2, 3, 4, 512, 512]);
  });

  it('swallows abort errors in onTileError, rethrows others', () => {
    const src = new AnywidgetPixelSource(
      mockModel(() => {}),
      { shape: SHAPE, dtype: 'Uint16', tileSize: 512 },
    );
    expect(() => src.onTileError(new Error('aborted'))).not.toThrow();
    expect(() => src.onTileError(new Error('network down'))).toThrow(/network down/);
  });

  it('getRaster uses labels to find y/x extents (no t axis)', async () => {
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 2, h: 2, dtype: 'uint8' },
        [new Uint8Array([1, 2, 3, 4]).buffer]));
    });
    const src = new AnywidgetPixelSource(model, {
      shape: [3, 2, 2], dtype: 'Uint8', tileSize: 2, labels: ['z', 'y', 'x'],
    });
    const out = await src.getRaster({ selection: { z: 1 }, signal: new AbortController().signal });
    expect(out.width).toBe(2);
    expect(out.height).toBe(2);
    expect(Array.from(out.data)).toEqual([1, 2, 3, 4]);
  });

  it('abort-then-reply still caches: a later getTile for the same key resolves without another send', async () => {
    let capturedMsg = null;
    const model = mockModel((msg) => { capturedMsg = msg; });
    const src = new AnywidgetPixelSource(model, { shape: SHAPE, dtype: 'Uint16', tileSize: 512 });
    const ac = new AbortController();
    const p = src.getTile({ x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: ac.signal });
    ac.abort();
    await expect(p).rejects.toThrow(/abort/i);

    // Let the debounced flush actually deliver the queued request to "Python".
    await new Promise((resolve) => { setTimeout(resolve, 0); });
    expect(capturedMsg).not.toBeNull();

    // Python's reply arrives after the caller already gave up — it should
    // still populate the cache for the next caller.
    model.emit('msg:custom',
      { kind: 'chunk', requestId: capturedMsg.requestId, ok: true, w: 2, h: 2, dtype: 'uint16' },
      [new Uint16Array([5, 6, 7, 8]).buffer]);

    const sendCountBefore = model.sendCount;
    const out = await src.getTile({
      x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    });
    expect(model.sendCount).toBe(sendCountBefore);
    expect(Array.from(out.data)).toEqual([5, 6, 7, 8]);
  });

  it('in-flight dedup: two concurrent getTile for the same key send exactly once', async () => {
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 2, h: 2, dtype: 'uint16' },
        [new Uint16Array([1, 2, 3, 4]).buffer]));
    });
    const src = new AnywidgetPixelSource(model, { shape: SHAPE, dtype: 'Uint16', tileSize: 512 });
    const sel = { t: 0, c: 0, z: 0 };
    const p1 = src.getTile({ x: 0, y: 0, selection: sel, signal: new AbortController().signal });
    const p2 = src.getTile({ x: 0, y: 0, selection: sel, signal: new AbortController().signal });
    const [out1, out2] = await Promise.all([p1, p2]);
    expect(model.sendCount).toBe(1);
    expect(Array.from(out1.data)).toEqual(Array.from(out2.data));
  });

  it('destroy rejects pending getTile calls', async () => {
    const model = mockModel(() => {}); // never replies
    const src = new AnywidgetPixelSource(model, { shape: SHAPE, dtype: 'Uint16', tileSize: 512 });
    const p = src.getTile({
      x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    });
    src.destroy();
    await expect(p).rejects.toThrow(/destroyed/);
    await p.catch((err) => expect(err.name).toBe('AbortError'));
  });

  it('DataView buffers with odd offset are copied, not viewed', async () => {
    const ab = new ArrayBuffer(7);
    const dv = new DataView(ab, 1, 4);
    new Uint8Array(ab).set([9, 1, 0, 2, 0, 8, 8]);
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 2, h: 1, dtype: 'uint16' },
        [dv]));
    });
    const src = new AnywidgetPixelSource(model, { shape: SHAPE, dtype: 'Uint16', tileSize: 512 });
    const out = await src.getTile({
      x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    });
    expect(Array.from(out.data)).toEqual([1, 2]);
    expect(out.data.buffer).not.toBe(ab);
  });

  it('LRU evicts the oldest entry once cacheSize is exceeded', async () => {
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 1, h: 1, dtype: 'uint16' },
        [new Uint16Array([msg.tx]).buffer]));
    });
    const src = new AnywidgetPixelSource(model, {
      shape: SHAPE, dtype: 'Uint16', tileSize: 512, cacheSize: 2,
    });
    const sel = { t: 0, c: 0, z: 0 };
    const sig = () => new AbortController().signal;
    await src.getTile({ x: 0, y: 0, selection: sel, signal: sig() }); // A
    await src.getTile({ x: 1, y: 0, selection: sel, signal: sig() }); // B
    await src.getTile({ x: 2, y: 0, selection: sel, signal: sig() }); // C -> evicts A

    const sendCountBeforeA = model.sendCount;
    await src.getTile({ x: 0, y: 0, selection: sel, signal: sig() }); // A again: was evicted
    expect(model.sendCount).toBe(sendCountBeforeA + 1);

    const sendCountBeforeC = model.sendCount;
    await src.getTile({ x: 2, y: 0, selection: sel, signal: sig() }); // C: still cached
    expect(model.sendCount).toBe(sendCountBeforeC);
  });
});
