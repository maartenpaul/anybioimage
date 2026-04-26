// anybioimage/frontend/viewer/src/interaction/keyboard.js
const TOOL_KEYS = {
  v: 'select', p: 'pan',
  r: 'rect', g: 'polygon', o: 'point',  // Phase 2 — sent but ignored until Phase 2
  l: 'line', m: 'areaMeasure',
};

function isEditableTarget(el) {
  if (!el) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  return false;
}

/**
 * Install keyboard shortcuts on a specific DOM element so that two widgets on
 * the same page do not fight each other [spec §5.2].
 *
 *   installKeyboard(model, containerEl)
 *     model       — the anywidget model for this viewer instance
 *     containerEl — the focusable root (tabIndex=0) of this widget; the
 *                   listener is attached here, not on window
 *
 * Returns a disposer that removes the listener.
 */
export function installKeyboard(model, containerEl) {
  if (!containerEl) {
    // Defensive: if the caller forgot to pass an element, do nothing and
    // return a no-op disposer. Fail loudly via console so we notice.
    console.error('installKeyboard: containerEl is required (spec §5.2)');
    return () => {};
  }

  function wrap(v, n) { return ((v % n) + n) % n; }

  function handler(e) {
    if (e.defaultPrevented) return;
    if (isEditableTarget(document.activeElement)) return;

    const dimT = model.get('dim_t') || 1;
    const dimZ = model.get('dim_z') || 1;
    const channels = model.get('_channel_settings') || [];
    const t = model.get('current_t') ?? 0;
    const z = model.get('current_z') ?? 0;
    const c = model.get('current_c') ?? 0;

    let consumed = true;
    switch (e.key) {
      case 'ArrowRight': model.set('current_t', wrap(t + 1, dimT)); break;
      case 'ArrowLeft':  model.set('current_t', wrap(t - 1, dimT)); break;
      case 'ArrowUp':    model.set('current_z', wrap(z + 1, dimZ)); break;
      case 'ArrowDown':  model.set('current_z', wrap(z - 1, dimZ)); break;
      case '[':          model.set('current_c', wrap(c - 1, channels.length || 1)); break;
      case ']':          model.set('current_c', wrap(c + 1, channels.length || 1)); break;
      case ',':          model.set('image_brightness', Math.max(-1, (model.get('image_brightness') ?? 0) - 0.05)); break;
      case '.':          model.set('image_brightness', Math.min( 1, (model.get('image_brightness') ?? 0) + 0.05)); break;
      default:
        if (e.ctrlKey && (e.key === 'z' || e.key === 'Z')) {
          model.send({ kind: 'undo', redo: e.shiftKey });
        } else if (TOOL_KEYS[e.key]) {
          model.set('tool_mode', TOOL_KEYS[e.key]);
        } else {
          consumed = false;
        }
    }
    if (consumed) { model.save_changes(); e.preventDefault(); }
  }

  containerEl.addEventListener('keydown', handler);
  return () => containerEl.removeEventListener('keydown', handler);
}
