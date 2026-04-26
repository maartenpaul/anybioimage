/**
 * AnywidgetPixelSource — implements Viv's PixelSource interface by requesting
 * chunks from Python over the anywidget message channel.
 *
 * Protocol:
 *   JS → Py : { kind: "chunk", requestId, t, c, z, level, tx, ty, tileSize }
 *   Py → JS : { kind: "chunk", requestId, ok, w, h, dtype } + buffers[0] (raw bytes)
 *
 * Dtype strings from Python (numpy) are one of: "uint8", "uint16", "uint32", "float32".
 * Viv expects "Uint8" | "Uint16" | "Uint32" | "Float32" in its PixelSource `dtype`.
 *
 * Caching:
 *   - JS-side LRU tile cache: completed responses served instantly.
 *   - In-flight deduplication: same tile requested while in-flight → second
 *     caller piggybacks on the first Python round-trip.
 */
import { trace } from '../../util/perf.js';

const DTYPE_TO_VIV = {
  uint8: 'Uint8', uint16: 'Uint16', uint32: 'Uint32', float32: 'Float32',
};

const VIV_TO_ARRAY = {
  Uint8: Uint8Array, Uint16: Uint16Array, Uint32: Uint32Array, Float32: Float32Array,
};

let _nextRequestId = 1;

// JS-side LRU tile cache cap. Each entry is a {data, width, height} object.
// For a 5T×3Z×3C image at 512px tiles this is 45 tiles total; 512 is
// comfortably above the worst-case for a single viewer session.
const JS_TILE_LRU_CAP = 512;

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

/**
 * Build a string cache key for a tile request.
 * Format: "t:c:z:level:tx:ty:tile"
 */
function tileKey(t, c, z, level, tx, ty, tile) {
  return `${t}:${c}:${z}:${level}:${tx}:${ty}:${tile}`;
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

    // JS-side LRU tile cache — Map<key, {data, width, height}>. Insertion
    // order = LRU; touch on hit by delete+re-insert.
    this._tileCache = new Map();

    // In-flight deduplication: maps cacheKey → array of {resolve, reject}
    // waiters. A second getTile for a key already in-flight joins the
    // waiter list instead of sending a duplicate request to Python.
    this._inFlight = new Map();

    // Maps requestId → cacheKey so the listener can cache even after an
    // aborted caller has rejected — the Python reply still arrives and
    // populates the cache for the next caller.
    this._reqToKey = new Map();

    this._listener = (content, buffers) => {
      if (!content || content.kind !== 'chunk') return;
      const cacheKey = this._reqToKey.get(content.requestId);
      const entry = this._pending.get(content.requestId);

      if (entry) this._pending.delete(content.requestId);
      if (cacheKey) this._reqToKey.delete(content.requestId);

      if (!content.ok) {
        // Error: reject the original entry; notify dedup waiters.
        const err = new Error(content.error || 'chunk fetch failed');
        if (entry) entry.reject(err);
        if (cacheKey) {
          const waiters = this._inFlight.get(cacheKey);
          if (waiters) {
            this._inFlight.delete(cacheKey);
            for (const w of waiters) w.reject(err);
          }
        }
        return;
      }

      // Success: build tile, cache it, resolve all waiters.
      const Ctor = VIV_TO_ARRAY[this._dtype] || Uint8Array;
      const tile = {
        data: toTypedArray(buffers && buffers[0], Ctor),
        width: content.w,
        height: content.h,
      };

      if (cacheKey) {
        this._tileCache.delete(cacheKey);   // re-insert at end (LRU touch)
        this._tileCache.set(cacheKey, tile);
        if (this._tileCache.size > JS_TILE_LRU_CAP) {
          this._tileCache.delete(this._tileCache.keys().next().value);
        }

        // Resolve all dedup waiters for this key.
        const waiters = this._inFlight.get(cacheKey);
        if (waiters) {
          this._inFlight.delete(cacheKey);
          for (const w of waiters) w.resolve(tile);
        }
      }

      if (entry) entry.resolve(tile);
    };
    model.on('msg:custom', this._listener);
  }

  destroy() {
    this._model.off('msg:custom', this._listener);
    const destroyErr = new Error('pixel source destroyed');
    for (const entry of this._pending.values()) {
      entry.reject(destroyErr);
    }
    this._pending.clear();
    this._reqToKey.clear();
    for (const waiters of this._inFlight.values()) {
      for (const w of waiters) w.reject(destroyErr);
    }
    this._inFlight.clear();
    if (this._flushTimer !== null) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
    this._pendingBatch = [];
    this._tileCache.clear();
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
    const t = selection.t | 0;
    const c = selection.c | 0;
    const z = selection.z | 0;
    const key = tileKey(t, c, z, this._level, x | 0, y | 0, this._tileSize);

    // Cache hit: serve immediately, no Python round-trip.
    const cached = this._tileCache.get(key);
    if (cached) {
      this._tileCache.delete(key);
      this._tileCache.set(key, cached);
      return cached;
    }

    // In-flight: join the existing request rather than duplicating it.
    const inFlightWaiters = this._inFlight.get(key);
    if (inFlightWaiters) {
      return new Promise((resolve, reject) => {
        const onAbort = () => {
          // Remove from waiter list; the original request continues in Python.
          const waiters = this._inFlight.get(key);
          if (waiters) {
            const idx = waiters.findIndex((w) => w.resolve === resolve);
            if (idx !== -1) waiters.splice(idx, 1);
          }
          reject(new Error('aborted'));
        };
        const waiter = { resolve, reject };
        inFlightWaiters.push(waiter);
        if (signal) {
          if (signal.aborted) { onAbort(); return; }
          signal.addEventListener('abort', onAbort, { once: true });
        }
      });
    }

    // New in-flight request — register dedup waiter list before sending.
    this._inFlight.set(key, []);

    const requestId = _nextRequestId++;
    // Register requestId → cacheKey BEFORE any abort path so the listener can
    // cache the response even if the caller aborts before Python replies.
    this._reqToKey.set(requestId, key);
    return new Promise((resolve, reject) => {
      const onAbort = () => {
        this._pending.delete(requestId);
        // Leave _reqToKey + _inFlight so the response is still cached on arrival.
        reject(new Error('aborted'));
      };
      if (signal) {
        if (signal.aborted) { this._reqToKey.delete(requestId); this._inFlight.delete(key); return onAbort(); }
        signal.addEventListener('abort', onAbort, { once: true });
      }
      this._pending.set(requestId, {
        resolve: (val) => { if (signal) signal.removeEventListener('abort', onAbort); resolve(val); },
        reject: (err) => { if (signal) signal.removeEventListener('abort', onAbort); reject(err); },
      });
      this._pendingBatch.push({
        kind: 'chunk',
        requestId,
        t,
        c,
        z,
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
