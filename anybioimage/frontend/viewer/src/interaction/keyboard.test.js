/** @vitest-environment jsdom */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { installKeyboard } from './keyboard.js';

function makeModel(state) {
  const listeners = {};
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; },
    save_changes: vi.fn(),
    on: (name, cb) => { listeners[name] = cb; },
    off: () => {},
    send: vi.fn(),
  };
}

describe('installKeyboard', () => {
  let dispose;
  let state;
  let model;
  beforeEach(() => {
    state = { current_t: 0, current_z: 0, dim_t: 5, dim_z: 3, current_c: 0,
              _channel_settings: [{ visible: true }, { visible: true }] };
    model = makeModel(state);
    dispose = installKeyboard(model);
  });
  afterEach(() => { dispose && dispose(); });

  it('ArrowRight advances T', () => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    expect(state.current_t).toBe(1);
  });

  it('[ decrements active channel with wrap', () => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: '[' }));
    expect(state.current_c).toBe(1);  // wrap from 0 to last
  });

  it('ignores key when focus is in an input', () => {
    const inp = document.createElement('input');
    document.body.appendChild(inp);
    inp.focus();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(state.current_t).toBe(0);
    inp.remove();
  });
});
