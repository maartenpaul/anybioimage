"""Channel names and pixel_size_um must be populated correctly."""
import numpy as np

from anybioimage import BioImageViewer
from anybioimage.mixins.image_loading import _channel_settings_from_omero


def test_channel_names_from_omero():
    ome = {"omero": {"channels": [
        {"label": "DAPI", "color": "0000FF", "window": {"start": 0, "end": 1000, "min": 0, "max": 65535}},
        {"label": "GFP", "color": "00FF00", "window": {"start": 0, "end": 500, "min": 0, "max": 65535}},
    ]}}
    settings = _channel_settings_from_omero(ome, dim_c=2, dtype=np.uint16)
    assert settings[0]["name"] == "DAPI"
    assert settings[1]["color"].lower() == "#00ff00"


def test_default_channel_names_for_numpy():
    v = BioImageViewer()
    v.set_image(np.zeros((1, 3, 1, 32, 32), dtype=np.uint8))
    names = [c["name"] for c in v._channel_settings]
    assert names == ["Ch 0", "Ch 1", "Ch 2"]


def test_pixel_size_um_none_for_numpy():
    v = BioImageViewer()
    v.set_image(np.zeros((1, 1, 1, 10, 10), dtype=np.uint8))
    assert v.pixel_size_um is None
