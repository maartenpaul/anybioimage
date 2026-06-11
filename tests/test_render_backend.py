import pytest

from anybioimage import BioImageViewer


def test_default_backend_is_canvas2d():
    v = BioImageViewer()
    assert v._render_backend == "canvas2d"
    assert v._zarr_source == {}
    assert v._render_ready is False


def test_explicit_canvas2d():
    v = BioImageViewer(render_backend="canvas2d")
    assert v._render_backend == "canvas2d"


def test_viv_backend_selects_viv_esm():
    from anybioimage.backends import get_backend_esm
    try:
        viv_esm = get_backend_esm("viv")
    except RuntimeError:
        pytest.skip("viv bundle not built yet")
    v = BioImageViewer(render_backend="viv")
    assert v._render_backend == "viv"
    assert v._esm == viv_esm
    assert v._esm != get_backend_esm("canvas2d")


def test_unknown_backend_raises():
    with pytest.raises(ValueError, match="vulkan"):
        BioImageViewer(render_backend="vulkan")
