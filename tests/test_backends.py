"""Tests for the backend registry."""

import pytest

import anybioimage
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


def test_canvas2d_backend_esm_matches_shipped_source_file():
    """The Canvas2D backend loader must return the exact bytes of shared/canvas2d.js."""
    from pathlib import Path

    import anybioimage.backends.canvas2d as canvas2d_mod

    shared = Path(anybioimage.__file__).parent / "frontend" / "shared" / "canvas2d.js"
    assert shared.is_file()
    expected = shared.read_text(encoding="utf-8")
    assert canvas2d_mod.load_esm() == expected


def test_viv_backend_esm_matches_shipped_bundle():
    from pathlib import Path

    import anybioimage.backends.viv as viv_mod

    bundle = Path(anybioimage.__file__).parent / "frontend" / "viv" / "dist" / "viv-bundle.js"
    assert bundle.is_file(), "build Task 14 must have committed dist/viv-bundle.js"
    assert viv_mod.load_esm() == bundle.read_text(encoding="utf-8")
