import { describe, it, expect, vi, beforeEach } from 'vitest';
import { InteractionController } from './InteractionController.js';

function fakeModel(initial = {}) {
  const state = { ...initial };
  const listeners = {};
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; (listeners[`change:${k}`] || []).forEach((cb) => cb({ new: v })); },
    on: (evt, cb) => { (listeners[evt] = listeners[evt] || []).push(cb); },
    off: (evt, cb) => { listeners[evt] = (listeners[evt] || []).filter((x) => x !== cb); },
    save_changes: () => {},
    send: vi.fn(),
    _state: state,
  };
}

describe('InteractionController', () => {
  let model, controller;
  beforeEach(() => {
    model = fakeModel({ tool_mode: 'pan', _annotations: [], current_t: 0, current_z: 0 });
    controller = new InteractionController(model);
  });

  it('picks the active tool from tool_mode', () => {
    expect(controller.activeToolId).toBe('pan');
    model.set('tool_mode', 'rect');
    expect(controller.activeToolId).toBe('rect');
  });

  it('dispatches pointer events to the active tool', () => {
    const stubTool = {
      id: 'stub', cursor: 'crosshair',
      onPointerDown: vi.fn(),
      onPointerMove: vi.fn(),
      onPointerUp: vi.fn(),
      onKeyDown: vi.fn(),
      getPreviewLayer: () => null,
    };
    controller.register(stubTool);
    model.set('tool_mode', 'stub');
    controller.handlePointerEvent('down', { x: 1, y: 2 });
    controller.handlePointerEvent('move', { x: 3, y: 4 });
    controller.handlePointerEvent('up',   { x: 5, y: 6 });
    expect(stubTool.onPointerDown).toHaveBeenCalledTimes(1);
    expect(stubTool.onPointerMove).toHaveBeenCalledTimes(1);
    expect(stubTool.onPointerUp).toHaveBeenCalledTimes(1);
  });

  it('returns the preview layer from the active tool', () => {
    const layer = { isLayer: true };
    const stubTool = {
      id: 'stub', cursor: 'crosshair',
      onPointerDown: () => {}, onPointerMove: () => {}, onPointerUp: () => {},
      onKeyDown: () => {},
      getPreviewLayer: () => layer,
    };
    controller.register(stubTool);
    model.set('tool_mode', 'stub');
    expect(controller.getPreviewLayer()).toBe(layer);
  });

  it('falls back to a no-op tool when tool_mode is unknown', () => {
    model.set('tool_mode', 'does-not-exist');
    // Should not throw.
    expect(() => controller.handlePointerEvent('down', { x: 0, y: 0 })).not.toThrow();
    expect(controller.getPreviewLayer()).toBeNull();
  });

  it('notifies subscribers when preview layer changes', () => {
    const sub = vi.fn();
    controller.onPreviewChange(sub);
    controller.markPreviewDirty();
    expect(sub).toHaveBeenCalled();
  });
});
