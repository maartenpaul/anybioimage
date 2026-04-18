"""Tests for the Viv-backend plate FOV switching."""

from pathlib import Path

import pytest

from anybioimage import BioImageViewer

TEST_PLATE = Path(__file__).parent.parent / "examples" / "test_plate.zarr"


@pytest.fixture
def plate_viewer():
    if not TEST_PLATE.is_dir():
        pytest.skip(f"{TEST_PLATE} missing (run examples/create_test_plate.py)")
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_plate(str(TEST_PLATE))
    return viewer


def test_wells_populated(plate_viewer):
    assert len(plate_viewer.plate_wells) >= 1


def test_initial_zarr_source_points_at_fov(plate_viewer):
    url = plate_viewer._zarr_source.get("url", "")
    assert str(TEST_PLATE) in url
    assert plate_viewer.current_well in url.replace("/", "")


def test_fov_switch_updates_zarr_source(plate_viewer):
    if len(plate_viewer.plate_fovs) < 2:
        pytest.skip("test plate has only one FOV")
    before = plate_viewer._zarr_source.get("url")
    plate_viewer.current_fov = plate_viewer.plate_fovs[1]
    after = plate_viewer._zarr_source.get("url")
    assert before != after
    assert str(TEST_PLATE) in after


def test_fov_switch_does_not_call_set_bioimage_on_viv(plate_viewer, monkeypatch):
    """Switching FOV on the Viv backend must NOT call _set_bioimage (would load via BioImage)."""
    monkeypatch.setattr(
        plate_viewer, "_set_bioimage",
        lambda img: pytest.fail("_set_bioimage called on Viv backend"),
    )
    if len(plate_viewer.plate_fovs) < 2:
        pytest.skip("test plate has only one FOV")
    plate_viewer.current_fov = plate_viewer.plate_fovs[1]
