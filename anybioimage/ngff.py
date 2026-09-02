"""Lenient OME-NGFF metadata reader on top of zarr-python 3.

This is the ONE place that knows the NGFF attrs layout:
  * v0.4 and earlier keep ``multiscales`` / ``omero`` / ``plate`` / ``well``
    at the top level of the group attrs (zarr v2 ``.zattrs``).
  * v0.5 and later nest them under an ``ome`` key (zarr v3 ``zarr.json``).

Store formats and remote filesystems are zarr-python's job. Parsing is
deliberately lenient: real-world writers omit axes, leave transforms empty, or
list datasets that do not exist. A viewer must still open those files.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import zarr

logger = logging.getLogger(__name__)

_DEFAULT_AXES = ["t", "c", "z", "y", "x"]


class PlateError(ValueError):
    """Raised when an HCS plate is opened where a single image was expected."""


def parse_ome_attrs(attrs: dict) -> tuple[str, dict]:
    """Return ``(version, ome_block)`` from raw group attrs.

    ``ome_block`` is the dict holding ``multiscales`` / ``omero`` / ``plate`` /
    ``well`` — the attrs themselves for v0.4, ``attrs["ome"]`` for v0.5+.
    ``version`` is ``"unknown"`` when no block declares one.
    """
    attrs = dict(attrs or {})
    ome = attrs.get("ome")
    if isinstance(ome, dict) and ome:
        return str(ome.get("version") or "0.5"), ome
    multiscales = attrs.get("multiscales") or []
    if (
        isinstance(multiscales, list)
        and multiscales
        and isinstance(multiscales[0], dict)
        and multiscales[0].get("version")
    ):
        return str(multiscales[0]["version"]), attrs
    plate = attrs.get("plate")
    if isinstance(plate, dict) and plate.get("version"):
        return str(plate["version"]), attrs
    return "unknown", attrs


def open_group(src, storage_options: dict | None = None) -> zarr.Group:
    """Open ``src`` read-only: a ``zarr.Group``, local path, ``file://``,
    ``s3://``, ``gs://`` or ``http(s)://`` (the latter need fsspec backends)."""
    if isinstance(src, zarr.Group):
        return src
    src = str(src)
    is_remote = "://" in src and not src.lower().startswith("file://")
    kwargs = {"mode": "r"}
    if storage_options:
        kwargs["storage_options"] = storage_options
    try:
        return zarr.open_group(src, **kwargs)
    except ImportError as e:  # fsspec backend (s3fs / gcsfs / aiohttp) missing
        if is_remote:
            raise ImportError(
                f"Opening {src!r} needs an fsspec backend: pip install 'anybioimage[remote]' ({e})"
            ) from e
        raise


def read_ome_attrs(group: zarr.Group) -> tuple[str, dict]:
    """``parse_ome_attrs`` applied to a zarr group."""
    return parse_ome_attrs(dict(group.attrs))


def axes_from_multiscale(multiscale: dict, ndim: int) -> list[str]:
    """Axis names for a multiscale block, falling back to trailing TCZYX.

    Accepts v0.4 ``[{"name": "t", ...}]`` and v0.3 ``["t", ...]`` forms.
    Any mismatch with ``ndim`` uses the default so indexing stays sane.
    """
    raw = multiscale.get("axes") or []
    names = []
    for a in raw:
        name = a.get("name") if isinstance(a, dict) else a
        if name:
            names.append(str(name).lower())
    if len(names) != ndim:
        if ndim <= 5:
            return _DEFAULT_AXES[-ndim:]
        return [f"dim{i}" for i in range(ndim - 5)] + _DEFAULT_AXES
    return names


@dataclass
class NgffImage:
    """One multiscale image: native pyramid levels plus the metadata a viewer needs."""

    group: zarr.Group
    version: str
    axes: list[str]                       # e.g. ["t", "c", "z", "y", "x"]; y always precedes x
    levels: list[zarr.Array]              # level 0 first (full resolution)
    dtype: np.dtype                       # level-0 dtype in NATIVE byte order — reads must be cast (arr.astype(img.dtype)) before .tobytes()
    omero_channels: list[dict] = field(default_factory=list)

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(int(s) for s in self.levels[0].shape)

    def size(self, axis: str) -> int:
        """Extent along ``axis``; 1 when the store has no such axis."""
        return self.shape[self.axes.index(axis)] if axis in self.axes else 1


def is_plate_attrs(ome: dict) -> bool:
    return isinstance(ome.get("plate"), dict)


def is_plate(group: zarr.Group) -> bool:
    return is_plate_attrs(read_ome_attrs(group)[1])


def plate_layout(group: zarr.Group) -> dict:
    """The raw ``plate`` block (rows / columns / wells) of an HCS plate group."""
    _, ome = read_ome_attrs(group)
    if not is_plate_attrs(ome):
        raise ValueError("No HCS plate metadata in group")
    return ome["plate"]


def open_image(src, storage_options: dict | None = None) -> NgffImage:
    """Open a multiscale image group leniently.

    Raises ``PlateError`` for HCS plate roots and ``ValueError`` when no usable
    multiscale arrays exist.
    """
    group = open_group(src, storage_options)
    version, ome = read_ome_attrs(group)
    if is_plate_attrs(ome):
        raise PlateError(f"{src!r} is an HCS plate, not a single image; use viewer.set_plate()")
    multiscales = ome.get("multiscales") or []
    if not isinstance(multiscales, list) or not multiscales or not isinstance(multiscales[0], dict):
        raise ValueError(f"No multiscales metadata in {src!r}")
    ms = multiscales[0]

    levels: list[zarr.Array] = []
    seen_paths: set[str] = set()
    for ds in ms.get("datasets") or []:
        path = ds.get("path") if isinstance(ds, dict) else ds
        if path is None:
            continue
        try:
            node = group[str(path)]
        except (KeyError, FileNotFoundError):
            logger.warning("multiscales dataset %r missing in store; skipped", path)
            continue
        if not isinstance(node, zarr.Array):
            logger.warning("multiscales dataset %r is not an array; skipped", path)
            continue
        if levels and node.ndim != levels[0].ndim:
            logger.warning(
                "multiscales dataset %r has ndim %d != %d; skipped",
                path, node.ndim, levels[0].ndim,
            )
            continue
        if str(path) in seen_paths:
            logger.warning("multiscales dataset %r listed twice; skipped", path)
            continue
        seen_paths.add(str(path))
        levels.append(node)
    if not levels:
        raise ValueError(f"multiscales in {src!r} lists no readable arrays")

    axes = axes_from_multiscale(ms, levels[0].ndim)
    if "y" not in axes or "x" not in axes or axes.index("y") > axes.index("x"):
        raise ValueError(f"Unsupported axes order {axes}: need y before x")
    omero = ome.get("omero")
    channels = (
        [c for c in (omero.get("channels") or []) if isinstance(c, dict)]
        if isinstance(omero, dict) else []
    )
    dtype = np.dtype(levels[0].dtype).newbyteorder("=")
    return NgffImage(group, version, axes, levels, dtype, channels)
