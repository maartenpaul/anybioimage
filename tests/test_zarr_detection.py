"""Tests for the tolerant zarr-URL detector."""

import pytest

from anybioimage.mixins.image_loading import _looks_like_zarr_url


@pytest.mark.parametrize("source", [
    "https://example.com/my.ome.zarr",
    "https://example.com/my.ome.zarr/",
    "http://localhost:8000/plate.zarr",
    "file:///data/my.ome.zarr",
    "s3://bucket/key/my.ome.zarr",
    "/tmp/my.ome.zarr",
    "./examples/image.zarr",
    "https://example.com/MY.OME.ZARR",  # case-insensitive
    "https://example.com/my.zarr?versionId=abc123",  # query-string stripped
])
def test_url_shapes_detected_as_zarr(source):
    assert _looks_like_zarr_url(source) is True


@pytest.mark.parametrize("source", [
    "",
    "https://example.com/image.tif",
    "https://example.com/data.csv",
    "/tmp/image.png",
    "file:///data/movie.mp4",
    "/tmp/foo.zarr.bak",  # superstring suffix — must reject
])
def test_non_zarr_shapes_rejected(source):
    assert _looks_like_zarr_url(source) is False


def test_non_string_inputs_are_rejected():
    import numpy as np

    assert _looks_like_zarr_url(np.zeros((4, 4))) is False
    assert _looks_like_zarr_url(None) is False
    assert _looks_like_zarr_url(42) is False
