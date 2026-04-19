"""WidgetHandle — Playwright-driven API for talking to a rendered BioImageViewer.

Reaches into the marimo shadow-DOM [spec §4], finds the MARIMO-ANYWIDGET that
matches `widget_index`, and exposes:

  wait_for_ready   block until _render_ready flips True
  get_trait/set    read / write traitlets by round-tripping through model
  click_tool       click toolbar button by title prefix
  drag             synthesise a pointer-down / move / up gesture
  focus            click inside the widget (focuses the container for keyboard)
  perf_snapshot    getPerfReport() dict
  perf_p95         convenience
  clear_perf       clearPerf()
"""
from __future__ import annotations

import time
from typing import Any


_WIDGET_JS_PRELUDE = """
(index) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  return widgets[index] || null;
}
"""


_GET_TRAIT_JS = """
([index, name]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return null;
  return w._widget?.model?.get(name) ?? null;
}
"""


_SET_TRAIT_JS = """
([index, name, value]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w || !w._widget?.model) return false;
  w._widget.model.set(name, value);
  w._widget.model.save_changes();
  return true;
}
"""


_CANVAS_BOX_JS = """
(index) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return null;
  const c = w.shadowRoot.querySelector('canvas');
  if (!c) return null;
  const r = c.getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height };
}
"""


_CLICK_TOOL_JS = """
([index, titlePrefix]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return false;
  const btns = [...w.shadowRoot.querySelectorAll('button')];
  const target = btns.find(b => (b.title || b.getAttribute('aria-label') || '').startsWith(titlePrefix));
  if (!target) return false;
  target.click();
  return true;
}
"""


_FOCUS_WIDGET_JS = """
(index) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return false;
  const root = w.shadowRoot.querySelector('.bioimage-viewer');
  if (root && typeof root.focus === 'function') { root.focus(); return true; }
  return false;
}
"""


_PERF_REPORT_JS = """
() => {
  // perf.js is loaded per-widget; all widgets on the page share the same
  // module instance because the bundle is ES-module cached. First widget wins.
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
      if (window.__anybioimage_perf_report) return window.__anybioimage_perf_report();
    }
  }
  return {};
}
"""


_INSTALL_PERF_PROBE_JS = """
() => {
  // The App.jsx entry exposes perf helpers on window so tests can reach them
  // without walking the React tree. Set by Task 7 (entry.js wiring).
  window.__ANYBIOIMAGE_PERF = true;
}
"""


class WidgetHandle:
    def __init__(self, page, widget_index: int = 0) -> None:
        self._page = page
        self._idx = widget_index

    # ---- readiness ----

    def wait_for_ready(self, timeout_ms: int = 30000) -> None:
        """Block until _render_ready === True (spec §2)."""
        # Enable perf instrumentation up-front — cheap and harmless.
        self._page.evaluate(_INSTALL_PERF_PROBE_JS)
        # Poll the trait rather than subscribing; handles the race where the
        # trait flipped before we could attach a listener (spec §10).
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            ok = self._page.evaluate(_GET_TRAIT_JS, [self._idx, "_render_ready"])
            if ok is True:
                return
            self._page.wait_for_timeout(100)
        raise TimeoutError("widget did not reach _render_ready within timeout")

    # ---- trait I/O ----

    def get(self, name: str) -> Any:
        return self._page.evaluate(_GET_TRAIT_JS, [self._idx, name])

    def set(self, name: str, value: Any) -> None:
        ok = self._page.evaluate(_SET_TRAIT_JS, [self._idx, name, value])
        if not ok:
            raise RuntimeError(f"failed to set trait {name}")

    # ---- gesture helpers ----

    def canvas_box(self) -> dict:
        box = self._page.evaluate(_CANVAS_BOX_JS, self._idx)
        if not box:
            raise RuntimeError("canvas not found")
        return box

    def click_tool(self, title_prefix: str) -> None:
        ok = self._page.evaluate(_CLICK_TOOL_JS, [self._idx, title_prefix])
        if not ok:
            raise RuntimeError(f"tool button '{title_prefix}' not found")

    def focus(self) -> None:
        ok = self._page.evaluate(_FOCUS_WIDGET_JS, self._idx)
        if not ok:
            # Fall back to a canvas click — focuses the shadow root's root div.
            box = self.canvas_box()
            self._page.mouse.click(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)

    def drag(self, x0: float, y0: float, x1: float, y1: float, steps: int = 10) -> None:
        self._page.mouse.move(x0, y0)
        self._page.mouse.down()
        self._page.mouse.move(x1, y1, steps=steps)
        self._page.mouse.up()

    def key(self, name: str) -> None:
        self._page.keyboard.press(name)

    # ---- perf ----

    def clear_perf(self) -> None:
        self._page.evaluate("() => window.__anybioimage_perf_clear && window.__anybioimage_perf_clear()")

    def perf_snapshot(self) -> dict:
        return self._page.evaluate(_PERF_REPORT_JS) or {}

    def perf_p95(self, label: str) -> float:
        rpt = self.perf_snapshot()
        entry = rpt.get(label)
        if not entry:
            raise KeyError(f"no perf samples under label '{label}'")
        return float(entry["p95"])
