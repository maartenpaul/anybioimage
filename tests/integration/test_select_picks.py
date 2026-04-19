"""Select tool: click on a rect, selected_annotation_id matches; click empty, id cleared.

Root cause (spec §5.1): InteractionController._ctx is `{ model, controller }`
only; the `pickObject` closure the Select tool calls is not injected. This
test draws a rect, clicks the Select tool, clicks inside the rect's pixel
bounds, and asserts selected_annotation_id was set to the rect's id.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_select_picks_a_rect(widget):
    # Place a rect directly via the trait so we don't depend on rect-tool drag.
    # Rect coords are in image pixels. demo_small.py is 256×256.
    widget.set("_annotations", [{
        "id": "r_test",
        "kind": "rect",
        "geometry": [50.0, 50.0, 150.0, 150.0],
        "label": "",
        "color": "#ff0000",
        "visible": True,
        "t": 0,
        "z": 0,
        "created_at": "2026-04-19T00:00:00Z",
        "metadata": {},
    }])
    # Activate Select tool (title prefix "Select").
    widget.click_tool("Select")

    # Click near the rect's centroid in image coords. Map through the canvas:
    # the test demo's view fits the image; centroid ≈ image (100, 100).
    # We can't trivially map image→screen from Python, so click the canvas
    # center — the demo's OrthographicView default shows the whole image
    # and the centroid sits near the middle. Nudge 20% toward top-left so we
    # hit the rect (50..150 range, not the whole canvas).
    box = widget.canvas_box()
    cx = box["x"] + box["w"] * 0.40
    cy = box["y"] + box["h"] * 0.40
    widget._page.mouse.click(cx, cy)
    widget._page.wait_for_timeout(300)

    assert widget.get("selected_annotation_id") == "r_test"
    assert widget.get("selected_annotation_type") == "rect"


@pytest.mark.integration
def test_select_clears_on_empty_click(widget):
    widget.set("_annotations", [{
        "id": "r_test",
        "kind": "rect",
        "geometry": [10.0, 10.0, 40.0, 40.0],
        "label": "",
        "color": "#ff0000",
        "visible": True,
        "t": 0,
        "z": 0,
        "created_at": "2026-04-19T00:00:00Z",
        "metadata": {},
    }])
    widget.set("selected_annotation_id", "r_test")
    widget.click_tool("Select")

    # Click far from the rect (bottom-right corner).
    box = widget.canvas_box()
    widget._page.mouse.click(box["x"] + box["w"] * 0.95, box["y"] + box["h"] * 0.95)
    widget._page.wait_for_timeout(300)

    assert widget.get("selected_annotation_id") == ""
    assert widget.get("selected_annotation_type") == ""
