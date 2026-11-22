"""Public channel API: set_channel() and channels_df."""
import numpy as np
import pytest

from anybioimage import BioImageViewer


@pytest.fixture
def viewer():
    data = np.zeros((1, 2, 1, 32, 32), dtype=np.uint16)
    data[0, 0] = np.linspace(100, 1100, 32 * 32).reshape(32, 32)
    data[0, 1] = np.linspace(0, 4000, 32 * 32).reshape(32, 32)
    v = BioImageViewer()
    v.set_image(data)
    return v


def test_set_channel_color_name_visible(viewer):
    viewer.set_channel(1, name="GFP", color="#00ff00", visible=False)
    ch = viewer._channel_settings[1]
    assert (ch["name"], ch["color"], ch["visible"]) == ("GFP", "#00ff00", False)


def test_set_channel_triggers_redraw(viewer):
    before = viewer.image_data
    viewer.set_channel(0, color="#ff00ff")
    assert viewer.image_data != before


def test_contrast_limits_in_data_values(viewer):
    viewer.set_channel(0, contrast_limits=(350, 850))
    ch = viewer._channel_settings[0]
    assert ch["min"] == pytest.approx(0.25)
    assert ch["max"] == pytest.approx(0.75)
    row = viewer.channels_df.iloc[0]
    assert row.contrast_min == pytest.approx(350)
    assert row.contrast_max == pytest.approx(850)


def test_contrast_limits_clipped_to_data_range(viewer):
    viewer.set_channel(0, contrast_limits=(-50, 99999))
    ch = viewer._channel_settings[0]
    assert (ch["min"], ch["max"]) == (0.0, 1.0)


def test_bad_arguments(viewer):
    with pytest.raises(IndexError):
        viewer.set_channel(5, color="#ffffff")
    with pytest.raises(ValueError):
        viewer.set_channel(0, contrast_limits=(10, 10))


def test_channels_df_columns(viewer):
    df = viewer.channels_df
    assert list(df.columns) == ["index", "name", "color", "visible", "contrast_min",
                                "contrast_max", "data_min", "data_max"]
    assert len(df) == 2
