"""Mask management mixin for BioImageViewer."""

from collections import OrderedDict

import numpy as np
import pandas as pd

from ..utils import (
    MASK_COLORS,
    array_to_base64,
    labels_to_rgba,
)

# Rendered frames kept per stacked mask (LRU). A 2048x2048 label PNG is
# typically well under 1 MB, so this bounds memory while making scrubbing
# back and forth free after the first visit.
_MASK_FRAME_CACHE_SIZE = 64

_DIMS_ALIASES = {"YX": "YX", "TYX": "TYX", "ZYX": "ZYX", "TZYX": "TZYX"}


def _as_tzyx(labels: np.ndarray, dims: str | None, dim_t: int, dim_z: int) -> tuple[np.ndarray, str]:
    """Return ``(stack, dims)`` with ``stack`` shaped ``(nt, nz, Y, X)`` (a view).

    ``nt`` is 1 or ``dim_t`` and ``nz`` is 1 or ``dim_z``. Leading singleton
    axes are dropped first, and a TCZYX array with one channel is accepted.
    Raises ValueError when the label array cannot be matched to the image.
    """
    if dims is not None:
        key = str(dims).upper()
        if key not in _DIMS_ALIASES:
            raise ValueError(f"dims must be one of {sorted(_DIMS_ALIASES)}, got {dims!r}")
        dims = _DIMS_ALIASES[key]

    if labels.ndim == 5:
        if labels.shape[1] != 1:
            raise ValueError(
                f"5D labels are read as TCZYX and need a single channel; got shape {labels.shape}"
            )
        labels = labels[:, 0]
    if dims is None:
        while labels.ndim > 2 and labels.shape[0] == 1:
            labels = labels[0]
    elif labels.ndim > len(dims):
        while labels.ndim > len(dims) and labels.shape[0] == 1:
            labels = labels[0]

    shape_hint = f"image has T={dim_t}, Z={dim_z}"
    if labels.ndim == 2:
        if dims not in (None, "YX"):
            raise ValueError(f"dims={dims!r} does not fit 2D labels of shape {labels.shape}")
        return labels[np.newaxis, np.newaxis], "YX"

    if labels.ndim == 3:
        n = labels.shape[0]
        if dims is None:
            fits_t = dim_t > 1 and n == dim_t
            fits_z = dim_z > 1 and n == dim_z
            if fits_t and fits_z:
                raise ValueError(
                    f"Label stack of {n} frames matches both T and Z ({shape_hint}); "
                    "pass dims='TYX' or dims='ZYX'"
                )
            if not (fits_t or fits_z):
                raise ValueError(
                    f"Label stack of shape {labels.shape} has {n} frames but the {shape_hint}. "
                    "Pass a 2D label image, or a stack with one frame per time point or z-plane."
                )
            dims = "TYX" if fits_t else "ZYX"
        if dims == "TYX":
            if n != dim_t:
                raise ValueError(f"dims='TYX' needs {dim_t} frames, labels have {n} ({shape_hint})")
            return labels[:, np.newaxis], dims
        if dims == "ZYX":
            if n != dim_z:
                raise ValueError(f"dims='ZYX' needs {dim_z} frames, labels have {n} ({shape_hint})")
            return labels[np.newaxis], dims
        raise ValueError(f"dims={dims!r} does not fit 3D labels of shape {labels.shape}")

    if labels.ndim == 4:
        if dims not in (None, "TZYX"):
            raise ValueError(f"dims={dims!r} does not fit 4D labels of shape {labels.shape}")
        nt, nz = labels.shape[:2]
        if nt not in (1, dim_t) or nz not in (1, dim_z):
            raise ValueError(f"4D labels are read as TZYX; shape {labels.shape} does not fit the {shape_hint}")
        return labels, "TZYX"

    raise ValueError(f"Cannot use {labels.ndim}D labels of shape {labels.shape} as a mask")


class MaskManagementMixin:
    """Mixin class providing mask layer management for BioImageViewer.

    This mixin handles adding, removing, and updating mask layers,
    including support for contour rendering and opacity control.

    Attributes expected to be defined by the main class:
        - _mask_arrays: Dict storing raw label arrays by mask id
        - _mask_caches: Dict storing rendered versions by mask id
        - _masks_data: List of mask layer dicts (traitlet)
    """

    def add_mask(
        self,
        labels: np.ndarray,
        name: str | None = None,
        color: str | None = None,
        opacity: float = 0.5,
        visible: bool = True,
        contours_only: bool = False,
        contour_width: int = 1,
        dims: str | None = None,
    ) -> str:
        """Add a mask layer.

        A 2D label image is shown on every time point and z-plane. A label
        stack follows the T/Z sliders: (T, Y, X), (Z, Y, X) or (T, Z, Y, X),
        matched to the current image's T and Z sizes.

        Args:
            labels: Label array (0 is background): 2D, or a stack with one
                frame per time point and/or z-plane. Leading singleton axes are
                ignored; 5D input is read as TCZYX with one channel.
            name: Display name for the mask layer (auto-assigned if None)
            color: Hex color for the mask (auto-assigned if None)
            opacity: Opacity value 0-1
            visible: Whether the mask is visible
            contours_only: If True, show only contours instead of filled regions
            contour_width: Width of contours in pixels
            dims: Axis order of a 3D stack, ``"TYX"`` or ``"ZYX"``. Needed only
                when the image has as many time points as z-planes.

        Returns:
            The mask ID

        Raises:
            ValueError: If a label stack does not fit the image's T/Z sizes.
        """
        labels = np.asarray(labels)
        stack, stack_dims = _as_tzyx(labels, dims, self.dim_t, self.dim_z)

        mask_id = f"mask_{len(self._masks_data)}_{id(labels)}"

        if stack_dims != "YX":
            stacks = getattr(self, "_mask_stacks", None)
            if stacks is None:
                stacks = self._mask_stacks = {}
            stacks[mask_id] = stack
        labels = self._mask_frame(mask_id, stack)

        # Store the labels currently on screen (the frame for stacks)
        self._mask_arrays[mask_id] = labels

        # Auto-assign color
        if color is None:
            color = MASK_COLORS[len(self._masks_data) % len(MASK_COLORS)]

        # Auto-assign name
        if name is None:
            name = f"Mask {len(self._masks_data) + 1}"

        self._mask_caches[mask_id] = OrderedDict()
        data_b64 = self._render_mask(mask_id, labels, contours_only, contour_width)

        mask_entry = {
            "id": mask_id,
            "name": name,
            "data": data_b64,
            "visible": visible,
            "opacity": opacity,
            "color": color,
            "contours": contours_only,
            "contour_width": contour_width,
        }

        self._masks_data = [*self._masks_data, mask_entry]
        return mask_id

    def set_mask(
        self,
        labels: np.ndarray,
        name: str | None = None,
        contours_only: bool = False,
        contour_width: int = 1,
    ):
        """Set a single mask (convenience method, clears existing masks).

        For backward compatibility with single-mask API.

        Args:
            labels: 2D numpy array of label values
            name: Display name for the mask layer
            contours_only: If True, show only contours
            contour_width: Width of contours in pixels
        """
        self.clear_masks()
        self.add_mask(labels, name=name or "Mask", contours_only=contours_only, contour_width=contour_width)

    def remove_mask(self, mask_id: str):
        """Remove a mask layer by ID.

        Args:
            mask_id: The ID of the mask to remove
        """
        self._masks_data = [m for m in self._masks_data if m["id"] != mask_id]
        self._mask_arrays.pop(mask_id, None)
        self._mask_caches.pop(mask_id, None)
        getattr(self, "_mask_stacks", {}).pop(mask_id, None)

    def clear_masks(self):
        """Remove all mask layers."""
        self._masks_data = []
        self._mask_arrays = {}
        self._mask_caches = {}
        self._mask_stacks = {}

    # --- T/Z-aware stacks -------------------------------------------------

    def _mask_position(self, mask_id: str) -> tuple[int, int]:
        """(t, z) index into a mask stack for the current slider position;
        (0, 0) for 2D masks. Clamped so a later image with more planes
        cannot index out of range."""
        stack = getattr(self, "_mask_stacks", {}).get(mask_id)
        if stack is None:
            return 0, 0
        nt, nz = stack.shape[:2]
        t = min(self.current_t, nt - 1) if nt > 1 else 0
        z = min(self.current_z, nz - 1) if nz > 1 else 0
        return t, z

    def _mask_frame(self, mask_id: str, stack: np.ndarray) -> np.ndarray:
        t, z = self._mask_position(mask_id) if mask_id in getattr(self, "_mask_stacks", {}) else (0, 0)
        return stack[t, z]

    def _render_mask(self, mask_id: str, labels: np.ndarray, contours: bool, width: int) -> str:
        """base64 PNG of ``labels`` for ``mask_id``, cached per frame and style."""
        cache = self._mask_caches.get(mask_id)
        if not isinstance(cache, OrderedDict):
            cache = self._mask_caches[mask_id] = OrderedDict()
        key = (contours, width, *self._mask_position(mask_id))
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        data_b64 = array_to_base64(labels_to_rgba(labels, contours_only=contours, contour_width=width))
        cache[key] = data_b64
        while len(cache) > _MASK_FRAME_CACHE_SIZE:
            cache.popitem(last=False)
        return data_b64

    def _on_mask_position_change(self, change=None):
        """Show the frame of every stacked mask that matches the new T/Z."""
        stacks = getattr(self, "_mask_stacks", None)
        if not stacks:
            return
        updated, changed = [], False
        for mask in self._masks_data:
            stack = stacks.get(mask["id"])
            if stack is None:
                updated.append(mask)
                continue
            labels = self._mask_frame(mask["id"], stack)
            self._mask_arrays[mask["id"]] = labels
            data = self._render_mask(
                mask["id"], labels, mask.get("contours", False), mask.get("contour_width", 1)
            )
            if data != mask.get("data"):
                mask = {**mask, "data": data}
                changed = True
            updated.append(mask)
        if changed:
            self._masks_data = updated

    def update_mask_settings(self, mask_id: str, **kwargs):
        """Update settings for a mask layer.

        Args:
            mask_id: The mask ID to update
            **kwargs: Settings to update (name, color, opacity, visible, contours, contour_width)
        """
        updated = []
        for mask in self._masks_data:
            if mask["id"] == mask_id:
                new_mask = {**mask, **kwargs}

                # Regenerate if contour settings changed
                if "contours" in kwargs or "contour_width" in kwargs:
                    if mask_id in self._mask_arrays:
                        new_mask["data"] = self._render_mask(
                            mask_id,
                            self._mask_arrays[mask_id],
                            new_mask.get("contours", False),
                            new_mask.get("contour_width", 1),
                        )

                updated.append(new_mask)
            else:
                updated.append(mask)
        self._masks_data = updated

    def get_mask_ids(self) -> list[str]:
        """Get list of all mask IDs.

        Returns:
            List of mask ID strings
        """
        return [m["id"] for m in self._masks_data]

    @property
    def masks_df(self) -> pd.DataFrame:
        """Get mask layers as a pandas DataFrame.

        Returns:
            DataFrame with columns: id, name, visible, opacity, color, contours
        """
        if not self._masks_data:
            return pd.DataFrame(columns=["id", "name", "visible", "opacity", "color", "contours"])
        return pd.DataFrame([
            {k: v for k, v in m.items() if k != "data"}
            for m in self._masks_data
        ])
