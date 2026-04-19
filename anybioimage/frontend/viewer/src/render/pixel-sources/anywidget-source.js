/**
 * AnywidgetPixelSource — implements Viv's PixelSource interface by requesting
 * chunks from Python over the anywidget message channel.
 *
 * Protocol (spec §2):
 *   JS → Py : { kind: "chunk", requestId, t, c, z, level, tx, ty, tileSize }
 *   Py → JS : { kind: "chunk", requestId, ok, w, h, dtype } + buffers[0] (raw bytes)
 *
 * Dtype strings from Python (numpy) are one of: "uint8", "uint16", "uint32", "float32".
 * Viv expects "Uint8" | "Uint16" | "Uint32" | "Float32" in its PixelSource `dtype`.
 */
import { trace } from '../../util/perf.js';

const DTYPE_TO_VIV = {
  uint8: 'Uint8', uint16: 'Uint16', uint32: 'Uint32', float32: 'Float32',
};

const VIV_TO_ARRAY = {
  Uint8: Uint8Array, Uint16: Uint16Array, Uint32: Uint32Array, Float32: Float32Array,
};

let _nextRequestId = 1;

/**
 * anywidget delivers buffers as ArrayBuffer or DataView depending on the
 * transport. Build a typed-array view of the correct length in either case.
 */
function toTypedArray(buf, Ctor) {
  if (!buf) return new Ctor(0);
  if (buf instanceof ArrayBuffer) {
    return new Ctor(buf, 0, buf.byteLength / Ctor.BYTES_PER_ELEMENT);
  }
  // ArrayBuffer view (DataView or TypedArray).
  const backing = buf.buffer;
  const offset = buf.byteOffset | 0;
  const length = (buf.byteLength | 0) / Ctor.BYTES_PER_ELEMENT;
  return new Ctor(backing, offset, length);
}

export class AnywidgetPixelSource {
  constructor(model, { shape, dtype, tileSize = 512, level = 0, labels }) {
    this._model = model;
    this._level = level;
    this._tileSize = tileSize;
    this._dtype = dtype;
    this._shape = shape;
    this._labels = labels || ['t', 'c', 'z', 'y', 'x'];
    this._pending = new Map();

    // Deck.gl calls getTile once per visible tile per frame — often dozens at
    // once on fit-to-screen. setTimeout(0) coalesces them into one microtask
    // burst so Python can dedupe cache hits in a tight loop. We use setTimeout
    // instead of requestAnimationFrame so background-tab throttling doesn't
    // stall pending requests indefinitely.
    this._pendingBatch = [];
    this._flushTimer = null;

    this._listener = (content, buffers) => {
      if (!content || content.kind !== 'chunk') return;
      const entry = this._pending.get(content.requestId);
      if (!entry) return;
      this._pending.delete(content.requestId);
      if (!content.ok) {
        entry.reject(new Error(content.error || 'chunk fetch failed'));
        return;
      }
      const Ctor = VIV_TO_ARRAY[this._dtype] || Uint8Array;
      entry.resolve({
        data: toTypedArray(buffers && buffers[0], Ctor),
        width: content.w,
        height: content.h,
      });
    };
    model.on('msg:custom', this._listener);
  }

  destroy() {
    this._model.off('msg:custom', this._listener);
    for (const entry of this._pending.values()) {
      entry.reject(new Error('pixel source destroyed'));
    }
    this._pending.clear();
    if (this._flushTimer !== null) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
    this._pendingBatch = [];
  }

  get shape() { return this._shape; }
  get labels() { return this._labels; }
  get tileSize() { return this._tileSize; }
  get dtype() { return this._dtype; }

  _flush() {
    this._flushTimer = null;
    const batch = this._pendingBatch.splice(0);
    for (const msg of batch) this._model.send(msg);
  }

  async getTile(args) {
    // trace() wraps the whole promise including the wait for Python's reply.
    // Label used by integration perf tests [spec §3].
    return trace('pixelSource:getTile', () => this._getTile(args));
  }

  async _getTile({ x, y, selection, signal }) {
    const requestId = _nextRequestId++;
    return new Promise((resolve, reject) => {
      const onAbort = () => {
        this._pending.delete(requestId);
        reject(new Error('aborted'));
      };
      if (signal) {
        if (signal.aborted) return onAbort();
        signal.addEventListener('abort', onAbort, { once: true });
      }
      this._pending.set(requestId, {
        resolve: (val) => { if (signal) signal.removeEventListener('abort', onAbort); resolve(val); },
        reject: (err) => { if (signal) signal.removeEventListener('abort', onAbort); reject(err); },
      });
      this._pendingBatch.push({
        kind: 'chunk',
        requestId,
        t: selection.t | 0,
        c: selection.c | 0,
        z: selection.z | 0,
        level: this._level,
        tx: x | 0,
        ty: y | 0,
        tileSize: this._tileSize,
      });
      if (this._flushTimer === null) {
        this._flushTimer = setTimeout(() => this._flush(), 0);
      }
    });
  }

  onTileError(err) {
    if (err && err.message === 'aborted') return;
    throw err;
  }

  async getRaster({ selection, signal }) {
    const [, , , yLen, xLen] = this._shape;
    const w = xLen; const h = yLen;
    const Ctor = VIV_TO_ARRAY[this._dtype] || Uint8Array;
    const out = new Ctor(w * h);
    const tile = this._tileSize;
    const tilesX = Math.ceil(w / tile);
    const tilesY = Math.ceil(h / tile);
    const jobs = [];
    for (let ty = 0; ty < tilesY; ty++) {
      for (let tx = 0; tx < tilesX; tx++) {
        jobs.push(this.getTile({ x: tx, y: ty, selection, signal }).then((t) => {
          const x0 = tx * tile;
          const y0 = ty * tile;
          for (let row = 0; row < t.height; row++) {
            out.set(t.data.subarray(row * t.width, (row + 1) * t.width),
                    (y0 + row) * w + x0);
          }
        }));
      }
    }
    await Promise.all(jobs);
    return { data: out, width: w, height: h };
  }

  static dtypeFromPython(pythonDtype) {
    return DTYPE_TO_VIV[pythonDtype] || 'Uint16';
  }
}
