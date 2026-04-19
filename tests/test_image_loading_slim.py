"""After the slim-down, set_image() must NOT:
  - start a precompute thread
  - populate a tile cache
  - generate PNG thumbnails
  - set image_data traitlet to anything but ""
"""
import numpy as np
from anybioimage import BioImageViewer


def test_set_numpy_creates_chunk_bridge_mode():
    v = BioImageViewer()
    v.set_image(np.zeros((3, 2, 1, 100, 100), dtype=np.uint16))
    assert v._pixel_source_mode == "chunk_bridge"
    assert v._image_shape == {"t": 3, "c": 2, "z": 1, "y": 100, "x": 100}
    assert v._image_dtype == "Uint16"
    assert v._chunk_array is not None
    assert v.image_data == ""


def test_set_url_creates_zarr_mode():
    v = BioImageViewer()
    v.set_image("https://example.com/my.ome.zarr")
    assert v._pixel_source_mode == "zarr"
    assert v._zarr_source == {"url": "https://example.com/my.ome.zarr", "headers": {}}
    assert v._chunk_array is None


def test_no_precompute_attributes_exist():
    v = BioImageViewer()
    # These were removed with the Canvas2D compositor.
    assert not hasattr(v, "_composite_cache")
    assert not hasattr(v, "_tile_cache")
    assert not hasattr(v, "_precompute_all_composites")
    assert not hasattr(v, "use_jpeg_tiles")
