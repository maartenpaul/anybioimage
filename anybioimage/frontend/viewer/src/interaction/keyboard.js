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

export function installKeyboard(model) {
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

  window.addEventListener('keydown', handler);
  return () => window.removeEventListener('keydown', handler);
}
