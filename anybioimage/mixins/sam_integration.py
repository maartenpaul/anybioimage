"""SAM (Segment Anything Model) integration mixin for BioImageViewer."""

import logging

import numpy as np

from ..utils import array_to_base64, labels_to_rgba

logger = logging.getLogger(__name__)


class SAMIntegrationMixin:
    """Mixin class providing SAM segmentation integration for BioImageViewer.

    This mixin enables automatic segmentation using SAM (Segment Anything Model)
    triggered by drawing ROIs or placing points on the image.

    Attributes expected to be defined by the main class:
        - _sam_model: The loaded SAM model instance
        - _sam_enabled: Whether SAM is enabled
        - _sam_model_type: Type of SAM model loaded
        - _processed_roi_ids: Set of ROI IDs that have been processed
        - _processed_point_ids: Set of point IDs that have been processed
        - _sam_label_counter: Counter for unique label IDs
        - _sam_mask_id: ID of the SAM mask layer
        - _sam_labels_array: Combined labels array for SAM masks
        - _image_array: Current image array for SAM input
        - _mask_arrays: Dict storing raw label arrays by mask id
        - _mask_caches: Dict storing rendered versions by mask id
        - _masks_data: List of mask layer dicts (traitlet)
        - _annotations: Unified annotations list traitlet [spec §5]
        - _delete_sam_at: Coordinates for SAM label deletion (traitlet)
        - width, height: Image dimensions
        - add_mask: Method to add a mask layer
        - remove_mask: Method to remove a mask layer
        - observe: Traitlet observe method
        - unobserve: Traitlet unobserve method
    """

    def enable_sam(self, model_type: str = "mobile_sam"):
        """Enable SAM segmentation triggered by rectangle ROIs or points.

        Args:
            model_type: SAM model to use. Options:
                - "mobile_sam" (default, ~40MB, fastest)
                - "sam_b" (SAM base)
                - "sam_l" (SAM large)
                - "fast_sam" (FastSAM)

        Raises:
            ImportError: If ultralytics is not installed
            ValueError: If model_type is not recognized

        Note:
            Requires: pip install ultralytics
        """
        try:
            from ultralytics import SAM
        except ImportError:
            raise ImportError(
                "SAM requires ultralytics. Install with: pip install ultralytics"
            )

        # Model file mapping
        model_files = {
            "mobile_sam": "mobile_sam.pt",
            "sam_b": "sam_b.pt",
            "sam_l": "sam_l.pt",
            "fast_sam": "FastSAM-s.pt",
        }

        if model_type not in model_files:
            raise ValueError(f"Unknown model_type: {model_type}. Choose from {list(model_files.keys())}")

        self._sam_model = SAM(model_files[model_type])
        self._sam_enabled = True
        self._sam_model_type = model_type
        self._processed_roi_ids = set()
        self._processed_point_ids = set()
        self._sam_label_counter = 0
        self._sam_mask_id = None
        self._sam_labels_array = None

        # Phase 2 — observe the unified _annotations traitlet [spec §5].
        self.observe(self._on_annotations_changed, names=["_annotations"])

    def disable_sam(self):
        """Disable SAM segmentation and clean up resources."""
        self._sam_enabled = False
        self._sam_model = None
        self._sam_mask_id = None
        self._sam_labels_array = None
        self._sam_label_counter = 0
        try:
            self.unobserve(self._on_annotations_changed, names=["_annotations"])
        except ValueError:
            pass

    def clear_sam_masks(self):
        """Clear all SAM-generated masks and reset the label counter."""
        if self._sam_mask_id and self._sam_mask_id in [m["id"] for m in self._masks_data]:
            self.remove_mask(self._sam_mask_id)
        self._sam_mask_id = None
        self._sam_labels_array = None
        self._sam_label_counter = 0
        self._processed_roi_ids = set()
        self._processed_point_ids = set()

    def delete_sam_label_at(self, x: int, y: int):
        """Delete the SAM label at the given coordinates.

        Args:
            x: X coordinate in image space
            y: Y coordinate in image space
        """
        if self._sam_labels_array is None:
            return

        # Check bounds
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return

        # Get the label at this position
        label = self._sam_labels_array[y, x]
        if label == 0:
            return  # No label at this position

        # Remove this label from the array
        self._sam_labels_array[self._sam_labels_array == label] = 0

        # Check if any labels remain
        if np.max(self._sam_labels_array) == 0:
            # No labels left, remove the mask layer
            if self._sam_mask_id:
                self.remove_mask(self._sam_mask_id)
            self._sam_mask_id = None
            self._sam_labels_array = None
        else:
            # Update the mask layer
            self._update_sam_mask_layer()

    def _on_delete_sam_at(self, change):
        """Observer callback to delete SAM label at given coordinates.

        Args:
            change: Traitlet change dict with coordinates {x, y}
        """
        coords = change.get("new")
        if coords and isinstance(coords, dict) and "x" in coords and "y" in coords:
            self.delete_sam_label_at(int(coords["x"]), int(coords["y"]))

    def _on_annotations_changed(self, change):
        """Run SAM on any new rect or point in `_annotations`.

        Dispatches to the existing rect/point handlers. IDs already processed
        are skipped via `_processed_roi_ids` / `_processed_point_ids`.
        """
        if not getattr(self, "_sam_enabled", False):
            return
        new_list = change["new"] or []
        rois = [a for a in new_list if a.get("kind") == "rect"]
        points = [a for a in new_list if a.get("kind") == "point"]
        if rois:
            # translate rect entries back to the {id, x, y, width, height} shape
            # the existing _on_rois_changed helper expects.
            legacy = []
            for a in rois:
                x0, y0, x1, y1 = a["geometry"]
                legacy.append({
                    "id": a["id"], "x": x0, "y": y0,
                    "width": x1 - x0, "height": y1 - y0,
                })
            self._on_rois_changed({"new": legacy})
        if points:
            legacy = [{"id": a["id"], "x": a["geometry"][0], "y": a["geometry"][1]}
                      for a in points]
            self._on_points_changed({"new": legacy})

    def _on_rois_changed(self, change):
        """Observer callback when ROIs change (called by _on_annotations_changed).

        Args:
            change: Dict with "new" key containing list of {id, x, y, width, height} dicts
        """
        if not getattr(self, "_sam_enabled", False):
            return

        new_rois = change.get("new", [])
        if not new_rois:
            return

        # Find new ROIs that haven't been processed
        for roi in new_rois:
            roi_id = roi.get("id", "")
            if roi_id and roi_id not in self._processed_roi_ids:
                self._processed_roi_ids.add(roi_id)
                self._run_sam_on_roi(roi)

    def _on_points_changed(self, change):
        """Observer callback when points change (called by _on_annotations_changed).

        Args:
            change: Dict with "new" key containing list of {id, x, y} dicts
        """
        if not getattr(self, "_sam_enabled", False):
            return

        new_points = change.get("new", [])
        if not new_points:
            return

        # Find new points that haven't been processed
        for point in new_points:
            point_id = point.get("id", "")
            if point_id and point_id not in self._processed_point_ids:
                self._processed_point_ids.add(point_id)
                self._run_sam_on_point(point)

    def _prepare_sam_image(self) -> np.ndarray | None:
        """Prepare image array for SAM prediction.

        Returns:
            RGB numpy array ready for SAM, or None if not available
        """
        if not hasattr(self, "_sam_model") or self._sam_model is None:
            return None
        if not hasattr(self, "_image_array") or self._image_array is None:
            return None

        image = np.ascontiguousarray(self._image_array).copy()
        if image.ndim == 2:
            image = np.stack([image, image, image], axis=-1)
        return image

    def _add_sam_mask(self, mask_data: np.ndarray):
        """Add a new SAM mask to the labels array and update the mask layer.

        Args:
            mask_data: Binary mask array from SAM prediction
        """
        self._sam_label_counter += 1

        if self._sam_labels_array is None:
            self._sam_labels_array = np.zeros((self.height, self.width), dtype=np.uint16)

        new_mask_region = mask_data & (self._sam_labels_array == 0)
        self._sam_labels_array[new_mask_region] = self._sam_label_counter

        if self._sam_mask_id is None:
            self._sam_mask_id = self.add_mask(
                self._sam_labels_array,
                name="SAM Masks",
                opacity=0.5,
                contours_only=False,
            )
        else:
            self._update_sam_mask_layer()

    def _run_sam_on_roi(self, roi: dict):
        """Run SAM segmentation on a bounding box ROI.

        Args:
            roi: ROI dict with keys: id, x, y, width, height
        """
        image = self._prepare_sam_image()
        if image is None:
            return

        x1 = int(roi["x"])
        y1 = int(roi["y"])
        x2 = int(roi["x"] + roi["width"])
        y2 = int(roi["y"] + roi["height"])

        try:
            results = self._sam_model.predict(image, bboxes=[[x1, y1, x2, y2]], verbose=False)

            if results and len(results) > 0 and results[0].masks is not None:
                mask_data = results[0].masks.data[0].cpu().numpy().astype(bool)
                self._add_sam_mask(mask_data)
                self._annotations = [a for a in self._annotations if a.get("id") != roi["id"]]
        except Exception as e:
            logger.warning("SAM prediction failed: %s", e)

    def _run_sam_on_point(self, point: dict):
        """Run SAM segmentation on a point prompt.

        Args:
            point: Point dict with keys: id, x, y
        """
        image = self._prepare_sam_image()
        if image is None:
            return

        x = int(point["x"])
        y = int(point["y"])

        try:
            results = self._sam_model.predict(image, points=[[x, y]], labels=[1], verbose=False)

            if results and len(results) > 0 and results[0].masks is not None:
                mask_data = results[0].masks.data[0].cpu().numpy().astype(bool)
                self._add_sam_mask(mask_data)
                self._annotations = [a for a in self._annotations if a.get("id") != point["id"]]
        except Exception as e:
            logger.warning("SAM point prediction failed: %s", e)

    def _update_sam_mask_layer(self):
        """Update the SAM mask layer with new labels."""
        if self._sam_mask_id is None or self._sam_labels_array is None:
            return

        # Store raw labels
        self._mask_arrays[self._sam_mask_id] = self._sam_labels_array

        # Generate new RGBA
        rgba = labels_to_rgba(self._sam_labels_array, contours_only=False, contour_width=1)
        data_b64 = array_to_base64(rgba)

        # Update cache
        self._mask_caches[self._sam_mask_id] = {(False, 1): data_b64}

        # Update the mask data
        updated_masks = []
        for mask in self._masks_data:
            if mask["id"] == self._sam_mask_id:
                updated_masks.append({**mask, "data": data_b64})
            else:
                updated_masks.append(mask)
        self._masks_data = updated_masks
