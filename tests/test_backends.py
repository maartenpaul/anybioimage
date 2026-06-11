import pytest

from anybioimage.backends import KNOWN_BACKENDS, get_backend_esm


def test_known_backends():
    assert KNOWN_BACKENDS == ("canvas2d", "viv")


def test_canvas2d_esm_is_mains_chrome():
    esm = get_backend_esm("canvas2d")
    assert "export default { render }" in esm
    assert "function renderCanvas()" in esm
    assert "canvas-wrapper" in esm


def test_unknown_backend_raises():
    with pytest.raises(ValueError, match="vulkan"):
        get_backend_esm("vulkan")


def test_viv_loader_missing_bundle_or_bundle():
    # Bundle is built in a later task. Before that, the loader must raise a
    # helpful RuntimeError; after, it returns the bundle. Accept either.
    try:
        esm = get_backend_esm("viv")
    except RuntimeError as e:
        assert "npm" in str(e)
    else:
        assert "render" in esm
