"""Unified image loading — metadata only. Rendering is done by Viv on the GPU
from either a remote zarr URL (direct browser fetch) or a chunk-bridged numpy
array (see PixelSourceMixin)."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_ZARR_SUFFIXES = (".zarr", ".ome.zarr", ".zarr/")

_DTYPE_TO_JS = {
    "uint8": "Uint8", "uint16": "Uint16",
    "uint32": "Uint32", "float32": "Float32",
}


def _looks_like_zarr_url(s: str) -> bool:
    if not isinstance(s, str):
        return False
    stripped = s.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()
    return stripped.endswith(_ZARR_SUFFIXES)


def _channel_settings_from_omero(ome: dict, dim_c: int, dtype: Any = None) -> list[dict]:
    """Build channel_settings dicts from an OME-Zarr omero block (or defaults)."""
    dtype_min: float | None = None
    dtype_max: float | None = None
    if dtype is not None and np.issubdtype(np.dtype(dtype), np.integer):
        info = np.iinfo(np.dtype(dtype))
        dtype_min = float(info.min); dtype_max = float(info.max)
    omero = ome.get("omero") or {}
    omero_channels = omero.get("channels") or []
    default_palette = ["#ff0000", "#00ff00", "#0000ff", "#ff00ff", "#00ffff", "#ffff00"]
    out = []
    for i in range(dim_c):
        src = omero_channels[i] if i < len(omero_channels) else {}
        window = src.get("window") or {}
        omero_min = float(window.get("min", 0.0))
        omero_max = float(window.get("max", 65535.0))
        if dtype_min is not None:
            data_min, data_max = dtype_min, dtype_max
        else:
            data_min, data_max = omero_min, omero_max
        start = float(window.get("start", omero_min))
        end = float(window.get("end", omero_max))
        omero_span = max(omero_max - omero_min, 1.0)
        vmin = max(0.0, (start - omero_min) / omero_span)
        vmax = min(1.0, (end - omero_min) / omero_span)
        color_hex = src.get("color")
        if color_hex:
            color = color_hex if color_hex.startswith("#") else f"#{color_hex}"
        else:
            color = default_palette[i % len(default_palette)]
        out.append({
            "index": i,
            "name": src.get("label", f"Ch {i}"),
            "visible": True,
            "color_kind": "solid",
            "color": color,
            "lut": "viridis",
            "data_min": data_min,
            "data_max": data_max,
            "min": vmin,
            "max": vmax,
            "gamma": 1.0,
        })
    return out


class ImageLoadingMixin:
    """Metadata-only image loading. Route `set_image()` to one of three paths."""

    def set_image(self, data: Any, *, headers: dict | None = None) -> None:
        """Load an image. `data` may be:
          * str / path — filesystem path or URL; zarr detected by suffix.
          * numpy.ndarray — 2D (YX), 3D (CYX), 4D (CZYX) or 5D (TCZYX).
          * bioio.BioImage — any file supported by bioio.
        """
        if isinstance(data, str):
            if _looks_like_zarr_url(data):
                self._set_zarr_url(data, headers or {})
                return
            # Non-URL string — try to open with bioio if available.
            try:
                from bioio import BioImage
                bio = BioImage(data)
                self._set_bioimage(bio)
                return
            except Exception as exc:  # pragma: no cover
                raise ValueError(f"could not open {data!r}: {exc}") from exc
        if isinstance(data, np.ndarray):
            self._set_numpy_source(data)
            return
        # BioImage duck-typing (avoid hard import for optional dep).
        if hasattr(data, "dims") and hasattr(data, "get_image_data"):
            self._set_bioimage(data)
            return
        raise TypeError(f"unsupported image type: {type(data).__name__}")

    def _set_zarr_url(self, url: str, headers: dict) -> None:
        self._clear_image_state()
        self._zarr_source = {"url": url, "headers": headers}
        self._pixel_source_mode = "zarr"
        # Dim/channel traitlets are populated JS-side from the zarr metadata.

    def _set_numpy_source(self, arr: np.ndarray) -> None:
        self._clear_image_state()
        tczyx = _to_tczyx(arr)
        self._chunk_array = tczyx
        t, c, z, y, x = tczyx.shape
        self._image_shape = {"t": t, "c": c, "z": z, "y": y, "x": x}
        self._image_dtype = _DTYPE_TO_JS.get(str(tczyx.dtype), "Uint16")
        self.dim_t = t; self.dim_c = c; self.dim_z = z
        self.width = x; self.height = y
        self._channel_settings = _channel_settings_from_omero({}, dim_c=c, dtype=tczyx.dtype)
        self.pixel_size_um = None
        self._pixel_source_mode = "chunk_bridge"

    def _set_bioimage(self, bio: Any) -> None:
        arr = np.asarray(bio.get_image_data("TCZYX"))
        if arr.nbytes > 2 * 1024 ** 3:
            logger.warning(
                "Image exceeds 2 GB (%.2f GB) and will be eagerly loaded into RAM; "
                "consider converting to OME-Zarr for lazy tile access.",
                arr.nbytes / 1024 ** 3)
        self._set_numpy_source(arr)
        try:
            self.pixel_size_um = float(bio.physical_pixel_sizes.X)  # type: ignore[attr-defined]
        except Exception:
            self.pixel_size_um = None
        try:
            names = [c.Name for c in bio.ome_metadata.images[0].pixels.channels]  # type: ignore[attr-defined]
            for i, name in enumerate(names):
                if i < len(self._channel_settings):
                    self._channel_settings[i]["name"] = name
            # Re-emit to trigger sync.
            self._channel_settings = list(self._channel_settings)
        except Exception:
            pass

    def _clear_image_state(self) -> None:
        self._chunk_array = None
        if hasattr(self, "_chunk_cache"):
            self._chunk_cache.clear()
        self._pixel_source_mode = "none"
        self._image_shape = None
        self._zarr_source = {}


def _to_tczyx(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 5: return arr
    if arr.ndim == 4: return arr[None, ...]
    if arr.ndim == 3: return arr[None, :, None, :, :]
    if arr.ndim == 2: return arr[None, None, None, :, :]
    raise ValueError(f"unsupported ndim: {arr.ndim}")
