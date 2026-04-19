"""Proves the integration harness wiring works end-to-end [spec §4, §9 step 1].

The only assertion is that `_render_ready` flipped True — everything else is
covered by later tests. If this test fails, the harness is broken; no later
test can be trusted.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_render_ready_flips_true(widget):
    assert widget.get("_render_ready") is True


@pytest.mark.integration
def test_channel_settings_is_nonempty(widget):
    settings = widget.get("_channel_settings")
    assert isinstance(settings, list)
    assert len(settings) >= 1
