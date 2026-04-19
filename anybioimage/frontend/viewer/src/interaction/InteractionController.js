/**
 * InteractionController — central dispatcher for pointer / key events on the
 * DeckCanvas. Holds the active tool selected by the `tool_mode` traitlet and
 * forwards events. Tools mutate `_annotations` (only mutation surface other
 * than the Layers panel).
 *
 * Each registered tool exports:
 *   { id, cursor, onPointerDown, onPointerMove, onPointerUp, onKeyDown,
 *     getPreviewLayer }
 * `getPreviewLayer()` returns a deck.gl Layer (or null) that renders the
 * in-progress draw. `markPreviewDirty()` triggers a re-render in DeckCanvas.
 */
const NOOP_TOOL = {
  id: '__noop',
  cursor: 'default',
  onPointerDown() {},
  onPointerMove() {},
  onPointerUp() {},
  onKeyDown() {},
  getPreviewLayer() { return null; },
};

export class InteractionController {
  constructor(model) {
    this._model = model;
    this._tools = new Map();
    this._previewListeners = new Set();
    this._ctx = { model, controller: this };
  }

  register(tool) {
    this._tools.set(tool.id, tool);
  }

  get activeToolId() {
    return this._model.get('tool_mode') || 'pan';
  }

  get activeTool() {
    return this._tools.get(this.activeToolId) || NOOP_TOOL;
  }

  get cursor() {
    return this.activeTool.cursor || 'default';
  }

  handlePointerEvent(phase, event) {
    const tool = this.activeTool;
    try {
      if (phase === 'down') tool.onPointerDown(event, this._ctx);
      else if (phase === 'move') tool.onPointerMove(event, this._ctx);
      else if (phase === 'up') tool.onPointerUp(event, this._ctx);
    } catch (err) {
      // Tools should never throw at runtime; log so we can see regressions
      // without killing the canvas.
      console.error(`tool '${tool.id}' threw in ${phase}:`, err);
    }
  }

  handleKeyDown(event) {
    try {
      this.activeTool.onKeyDown(event, this._ctx);
    } catch (err) {
      console.error(`tool '${this.activeTool.id}' threw in keyDown:`, err);
    }
  }

  getPreviewLayer() {
    return this.activeTool.getPreviewLayer(this._ctx) || null;
  }

  onPreviewChange(cb) {
    this._previewListeners.add(cb);
    return () => this._previewListeners.delete(cb);
  }

  markPreviewDirty() {
    for (const cb of this._previewListeners) cb();
  }
}
