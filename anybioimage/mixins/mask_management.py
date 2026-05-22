"""Mask management mixin for BioImageViewer.

Phase 2 [spec §2, §3]: mask RGBA is no longer serialised as base64 PNG inside
`_masks_data`. Instead, raw RGBA bytes live in `_mask_bytes` on the Python
side; JS requests them lazily via `{kind: "mask_request", id}` and receives
them as an anywidget message buffer. `_masks_data` entries carry only
metadata.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import MASK_COLORS, labels_to_rgba


class MaskManagementMixin:
    """Mask layer management for BioImageViewer.

    Attributes expected on the concrete class:
        - `_mask_arrays`: dict[str, np.ndarray]  — raw label arrays
        - `_mask_bytes`:  dict[str, bytes]       — rendered RGBA bytes (transport)
        - `_mask_caches`: dict[str, dict]        — cache keyed by (contours, width)
        - `_masks_data`:  list[dict] (traitlet)  — metadata only
    """

    # ---- lifecycle helpers used by subclasses at init time ----
    def _ensure_mask_state(self) -> None:
        if not hasattr(self, "_mask_arrays"):
            self._mask_arrays = {}
        if not hasattr(self, "_mask_bytes"):
            self._mask_bytes = {}
        if not hasattr(self, "_mask_caches"):
            self._mask_caches = {}

    # ---- public API (unchanged signatures) ----
    def add_mask(
        self,
        labels: np.ndarray,
        name: str | None = None,
        color: str | None = None,
        opacity: float = 0.5,
        visible: bool = True,
        contours_only: bool = False,
        contour_width: int = 1,
    ) -> str:
        """Add a mask layer.

        Args:
            labels: 2D numpy array of label values (0 is background)
            name: Display name for the mask layer (auto-assigned if None)
            color: Hex color for the mask (auto-assigned if None)
            opacity: Opacity value 0-1
            visible: Whether the mask is visible
            contours_only: If True, show only contours instead of filled regions
            contour_width: Width of contours in pixels

        Returns:
            The mask ID
        """
        self._ensure_mask_state()
        if labels.ndim > 2:
            labels = labels.squeeze()
            if labels.ndim > 2:
                labels = labels[0] if labels.ndim == 3 else labels[0, 0]

        mask_id = f"mask_{len(self._masks_data)}_{id(labels)}"
        if color is None:
            color = MASK_COLORS[len(self._masks_data) % len(MASK_COLORS)]
        if name is None:
            name = f"Mask {len(self._masks_data) + 1}"

        rgba = labels_to_rgba(labels, contours_only=contours_only, contour_width=contour_width)
        rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
        h, w = rgba.shape[:2]

        self._mask_arrays[mask_id] = labels
        self._mask_bytes[mask_id] = rgba.tobytes()
        self._mask_caches[mask_id] = {(contours_only, contour_width): self._mask_bytes[mask_id]}

        entry = {
            "id": mask_id,
            "name": name,
            "width": int(w),
            "height": int(h),
            "dtype": "uint8",
            "visible": bool(visible),
            "opacity": float(opacity),
            "color": color,
            "contours": bool(contours_only),
            "contour_width": int(contour_width),
        }
        self._masks_data = [*self._masks_data, entry]

        # Push bytes immediately so the JS side does not need to request them.
        self._push_mask_bytes(mask_id)
        return mask_id

    def set_mask(
        self,
        labels: np.ndarray,
        name: str | None = None,
        contours_only: bool = False,
        contour_width: int = 1,
    ) -> None:
        """Set a single mask (convenience method, clears existing masks).

        For backward compatibility with single-mask API.

        Args:
            labels: 2D numpy array of label values
            name: Display name for the mask layer
            contours_only: If True, show only contours
            contour_width: Width of contours in pixels
        """
        self.clear_masks()
        self.add_mask(labels, name=name or "Mask",
                      contours_only=contours_only, contour_width=contour_width)

    def remove_mask(self, mask_id: str) -> None:
        """Remove a mask layer by ID.

        Args:
            mask_id: The ID of the mask to remove
        """
        self._ensure_mask_state()
        self._masks_data = [m for m in self._masks_data if m["id"] != mask_id]
        self._mask_arrays.pop(mask_id, None)
        self._mask_bytes.pop(mask_id, None)
        self._mask_caches.pop(mask_id, None)

    def clear_masks(self) -> None:
        """Remove all mask layers."""
        self._ensure_mask_state()
        self._masks_data = []
        self._mask_arrays = {}
        self._mask_bytes = {}
        self._mask_caches = {}

    def update_mask_settings(self, mask_id: str, **kwargs) -> None:
        """Update settings for a mask layer.

        Args:
            mask_id: The mask ID to update
            **kwargs: Settings to update (name, color, opacity, visible, contours, contour_width)
        """
        self._ensure_mask_state()
        updated = []
        regenerate = "contours" in kwargs or "contour_width" in kwargs
        for m in self._masks_data:
            if m["id"] != mask_id:
                updated.append(m)
                continue
            new_m = {**m, **kwargs}
            if regenerate and mask_id in self._mask_arrays:
                contours = new_m.get("contours", False)
                width = new_m.get("contour_width", 1)
                cache_key = (contours, width)
                cached = self._mask_caches.get(mask_id, {}).get(cache_key)
                if cached is None:
                    rgba = labels_to_rgba(
                        self._mask_arrays[mask_id],
                        contours_only=contours, contour_width=width,
                    )
                    rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
                    cached = rgba.tobytes()
                    self._mask_caches.setdefault(mask_id, {})[cache_key] = cached
                self._mask_bytes[mask_id] = cached
            updated.append(new_m)
        self._masks_data = updated
        if regenerate:
            self._push_mask_bytes(mask_id)

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
        keep = ["id", "name", "visible", "opacity", "color", "contours"]
        return pd.DataFrame([{k: m[k] for k in keep if k in m} for m in self._masks_data])

    # ---- transport ----
    def _push_mask_bytes(self, mask_id: str) -> None:
        """Send raw mask RGBA to JS over the anywidget message channel."""
        self._ensure_mask_state()
        meta = next((m for m in self._masks_data if m["id"] == mask_id), None)
        if not meta:
            return
        data = self._mask_bytes.get(mask_id)
        if data is None:
            return
        self.send(
            {"kind": "mask", "id": mask_id,
             "width": meta["width"], "height": meta["height"], "dtype": "uint8"},
            [data],
        )

    def handle_mask_request(self, payload: dict) -> None:
        """Handle a JS → Python mask_request message."""
        mid = payload.get("id")
        if not mid:
            return
        self._push_mask_bytes(mid)
