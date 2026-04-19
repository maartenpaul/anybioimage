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

const DTYPE_TO_VIV = {
  uint8: 'Uint8', uint16: 'Uint16', uint32: 'Uint32', float32: 'Float32',
};

const VIV_TO_ARRAY = {
  Uint8: Uint8Array, Uint16: Uint16Array, Uint32: Uint32Array, Float32: Float32Array,
};

let _nextRequestId = 1;

export class AnywidgetPixelSource {
  constructor(model, { shape, dtype, tileSize = 512, level = 0, labels }) {
    this._model = model;
    this._level = level;
    this._tileSize = tileSize;
    this._dtype = dtype;
    // Accept shape as either array [t,c,z,y,x] or object {t,c,z,y,x}
    this._shape = Array.isArray(shape)
      ? { t: shape[0], c: shape[1], z: shape[2], y: shape[3], x: shape[4] }
      : shape;
    this._labels = labels || ['t', 'c', 'z', 'y', 'x'];
    this._pending = new Map();

    // rAF batching for coalescing rapid tile requests
    this._pendingBatch = [];
    this._rafId = null;

    // Register a single listener; multiplex by requestId.
    // anywidget exposes custom messages on 'msg:custom'.
    this._listener = (content, buffers) => {
      if (!content || content.kind !== 'chunk') return;
      const entry = this._pending.get(content.requestId);
      if (!entry) return;
      this._pending.delete(content.requestId);
      if (!content.ok) {
        entry.reject(new Error(content.error || 'chunk fetch failed'));
        return;
      }
      const Ctor = VIV_TO_ARRAY[dtype] || Uint8Array;
      const view = buffers && buffers[0]
        ? new Ctor(buffers[0])
        : new Ctor(0);
      entry.resolve({ data: view, width: content.w, height: content.h });
    };
    model.on('msg:custom', this._listener);
  }

  destroy() {
    this._model.off('msg:custom', this._listener);
    for (const entry of this._pending.values()) {
      entry.reject(new Error('pixel source destroyed'));
    }
    this._pending.clear();
    if (this._rafId !== null) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    this._pendingBatch = [];
  }

  get shape() {
    return [this._shape.t, this._shape.c, this._shape.z, this._shape.y, this._shape.x];
  }
  get labels() { return this._labels; }
  get tileSize() { return this._tileSize; }
  get dtype() { return this._dtype; }

  _flush() {
    this._rafId = null;
    const batch = this._pendingBatch.splice(0);
    for (const item of batch) {
      this._model.send({
        kind: 'chunk',
        requestId: item.requestId,
        t: item.t,
        c: item.c,
        z: item.z,
        level: item.level,
        tx: item.tx,
        ty: item.ty,
        tileSize: item.tileSize,
      });
    }
  }

  async getTile({ x, y, selection, signal }) {
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
        requestId,
        t: selection.t | 0,
        c: selection.c | 0,
        z: selection.z | 0,
        level: this._level,
        tx: x | 0,
        ty: y | 0,
        tileSize: this._tileSize,
      });
      if (this._rafId === null) {
        this._rafId = requestAnimationFrame(() => this._flush());
      }
    });
  }

  onTileError(err) {
    if (err && err.message === 'aborted') return;
    throw err;
  }

  async getRaster({ selection, signal }) {
    // Simple: reconstitute from tiles. Called rarely (histogram / auto).
    const w = this._shape.x;
    const h = this._shape.y;
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
