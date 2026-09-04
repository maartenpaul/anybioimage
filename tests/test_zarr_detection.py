"""Zarr input detectors: browser-fetchable URLs vs kernel-only paths."""
from pathlib import Path

import numpy as np
import pytest

from anybioimage.mixins.image_loading import _looks_like_zarr_path, _looks_like_zarr_url


@pytest.mark.parametrize("source", [
    "https://example.com/my.ome.zarr",
    "https://example.com/my.ome.zarr/",
    "http://localhost:8000/plate.zarr",
    "https://example.com/plate.ome.zarr/B/2/8",
    "https://example.com/MY.OME.ZARR",
    "https://example.com/my.zarr?versionId=abc123",
])
def test_http_urls_detected(source):
    assert _looks_like_zarr_url(source) is True
    assert _looks_like_zarr_path(source) is False


@pytest.mark.parametrize("source", [
    # Subgroups inside a store are images too: an HCS field is shared as
    # <plate>.zarr/<row>/<col>/<field>, so the suffix can be mid-path.
    "s3://bucket/plate.ome.zarr/B/2/8?anonymous=true",
    "/data/plate.zarr/B/2/8",
    "gs://bucket/x.zarr/labels/nuclei",
    "/tmp/my.ome.zarr",
    "./examples/image.zarr",
    "examples/image.zarr/",
    Path("/data/x.zarr"),
    "file:///data/my.ome.zarr",
    "s3://bucket/key/my.ome.zarr",
    "gs://bucket/my.zarr",
    "S3://BUCKET/X.ZARR",
])
def test_kernel_paths_detected(source):
    assert _looks_like_zarr_path(source) is True
    assert _looks_like_zarr_url(source) is False


@pytest.mark.parametrize("source", [
    "", "https://example.com/image.tif", "/tmp/image.png", "/tmp/foo.zarr.bak",
    "file:///data/movie.mp4", None, 42, np.zeros((4, 4)),
])
def test_non_zarr_rejected(source):
    assert _looks_like_zarr_url(source) is False
    assert _looks_like_zarr_path(source) is False
