/** MaskSourceBridge — receives raw mask RGBA over the anywidget message
 *  channel and publishes `{ id, width, height, pixels: Uint8Array }` entries
 *  to subscribers. One bridge per widget; created once in `App.jsx`.
 *
 *  Wire protocol (spec §3):
 *    JS → Py : { kind: "mask_request", id }
 *    Py → JS : { kind: "mask", id, width, height, dtype } + buffers[0]
 */
export class MaskSourceBridge {
  constructor(model) {
    this._model = model;
    this._entries = new Map();      // id → { width, height, pixels }
    this._subs = new Map();         // id → Set<callback>
    this._requested = new Set();
    this._listener = (content, buffers) => {
      if (!content || content.kind !== 'mask') return;
      const id = content.id;
      if (!id) return;
      const buf = buffers && buffers[0];
      if (!buf) return;
      const pixels = new Uint8Array(
        buf instanceof ArrayBuffer ? buf :
        buf.buffer ? buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) :
        buf
      );
      const entry = { width: content.width, height: content.height, pixels };
      this._entries.set(id, entry);
      // First-pass notify with pixels only so React knows something changed.
      for (const cb of this._subs.get(id) || []) cb(entry);
      this._bakeBitmap(entry).then(() => {
        for (const cb of this._subs.get(id) || []) cb(entry);
      });
    };
    model.on('msg:custom', this._listener);
  }

  get(id) { return this._entries.get(id); }

  subscribe(id, cb) {
    if (!this._subs.has(id)) this._subs.set(id, new Set());
    this._subs.get(id).add(cb);
    const cached = this._entries.get(id);
    if (cached) { cb(cached); }
    if (!this._requested.has(id)) {
      this._requested.add(id);
      this._model.send({ kind: 'mask_request', id });
    }
    return () => {
      const set = this._subs.get(id);
      if (set) { set.delete(cb); if (set.size === 0) this._subs.delete(id); }
    };
  }

  invalidate(id) {
    // Called when mask settings change (contour etc.) — refetch from Python.
    this._entries.delete(id);
    this._requested.delete(id);
    for (const cb of this._subs.get(id) || []) {
      this._requested.add(id);
      this._model.send({ kind: 'mask_request', id });
      break;   // one request is enough; subscribers all fire on the next emit
    }
  }

  async _bakeBitmap(entry) {
    if (entry.bitmap) return entry.bitmap;
    if (typeof ImageData !== 'undefined') {
      const imgData = new ImageData(new Uint8ClampedArray(entry.pixels), entry.width, entry.height);
      if (typeof createImageBitmap === 'function') {
        try {
          entry.bitmap = await createImageBitmap(imgData);
          return entry.bitmap;
        } catch { /* fall through to ImageData fallback */ }
      }
      // Fallback: use ImageData directly (works in environments without createImageBitmap).
      entry.bitmap = imgData;
    } else {
      // No ImageData available (non-browser non-jsdom environments): use pixels as sentinel.
      entry.bitmap = { _raw: entry.pixels, width: entry.width, height: entry.height };
    }
    return entry.bitmap;
  }

  destroy() {
    this._model.off('msg:custom', this._listener);
    this._entries.clear();
    this._subs.clear();
    this._requested.clear();
  }
}
