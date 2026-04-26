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
  let container;
  beforeEach(() => {
    state = { current_t: 0, current_z: 0, dim_t: 5, dim_z: 3, current_c: 0,
              _channel_settings: [{ visible: true }, { visible: true }] };
    model = makeModel(state);
    container = document.createElement('div');
    container.tabIndex = 0;
    document.body.appendChild(container);
    dispose = installKeyboard(model, container);
  });
  afterEach(() => {
    dispose && dispose();
    container.remove();
  });

  it('ArrowRight advances T', () => {
    container.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(state.current_t).toBe(1);
  });

  it('[ decrements active channel with wrap', () => {
    container.dispatchEvent(new KeyboardEvent('keydown', { key: '[', bubbles: true }));
    expect(state.current_c).toBe(1);  // wrap from 0 to last
  });

  it('ignores key when focus is in an input', () => {
    const inp = document.createElement('input');
    document.body.appendChild(inp);
    inp.focus();
    container.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(state.current_t).toBe(0);
    inp.remove();
  });

  it('does not respond to events on a second separate container', () => {
    const other = document.createElement('div');
    other.tabIndex = 0;
    document.body.appendChild(other);
    other.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(state.current_t).toBe(0);  // no change — event was on a different element
    other.remove();
  });

  it('returns a no-op disposer when containerEl is omitted', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const d = installKeyboard(model);
    expect(typeof d).toBe('function');
    expect(() => d()).not.toThrow();
    errSpy.mockRestore();
  });
});
