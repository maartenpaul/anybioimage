"""Keyboard shortcuts are scoped to the focused widget [spec §5.2].

Root cause: keyboard.js attaches its handler to `window`. Two widgets on a
page stack two listeners, both respond to every key.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_arrow_right_only_affects_focused_widget(widgets_two):
    a, b = widgets_two
    # Baseline.
    assert a.get("current_t") == 0
    assert b.get("current_t") == 0

    # Focus widget A, press ArrowRight → only A's current_t should advance.
    a.focus()
    a._page.wait_for_timeout(100)
    a.key("ArrowRight")
    a._page.wait_for_timeout(200)
    assert a.get("current_t") == 1, "widget A did not advance"
    assert b.get("current_t") == 0, "widget B advanced despite not being focused"

    # Focus widget B, press ArrowRight → only B's current_t should advance.
    b.focus()
    b._page.wait_for_timeout(100)
    b.key("ArrowRight")
    b._page.wait_for_timeout(200)
    assert a.get("current_t") == 1, "widget A's current_t moved while focus on B"
    assert b.get("current_t") == 1, "widget B did not advance"


@pytest.mark.integration
def test_tool_shortcut_only_affects_focused_widget(widgets_two):
    a, b = widgets_two
    assert a.get("tool_mode") == "pan"
    assert b.get("tool_mode") == "pan"

    a.focus()
    a._page.wait_for_timeout(100)
    a.key("r")   # Rectangle shortcut
    a._page.wait_for_timeout(200)
    assert a.get("tool_mode") == "rect"
    assert b.get("tool_mode") == "pan", "tool_mode leaked to non-focused widget B"
