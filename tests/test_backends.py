"""Tests for the backend registry."""

import pytest

from anybioimage.backends import get_backend_esm, KNOWN_BACKENDS


def test_known_backends_contains_canvas2d_and_viv():
    assert "canvas2d" in KNOWN_BACKENDS
    assert "viv" in KNOWN_BACKENDS


def test_get_backend_esm_canvas2d_returns_nonempty_string():
    esm = get_backend_esm("canvas2d")
    assert isinstance(esm, str)
    assert len(esm) > 0
    assert "export default" in esm


def test_get_backend_esm_viv_returns_nonempty_string():
    esm = get_backend_esm("viv")
    assert isinstance(esm, str)
    assert len(esm) > 0


def test_get_backend_esm_unknown_raises():
    with pytest.raises(ValueError, match="unknown render_backend"):
        get_backend_esm("opengl")
