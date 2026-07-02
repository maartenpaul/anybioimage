import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    from pathlib import Path

    import marimo as mo
    import numpy as np
    import pandas as pd
    from bioio import BioImage
    import bioio_tifffile
    from anybioimage import BioImageViewer

    def find_asset(name):
        """Resolve an asset whether marimo is launched from the repo root or examples/."""
        for base in (Path.cwd(), Path.cwd() / "examples"):
            candidate = base / name
            if candidate.exists():
                return str(candidate)
        return name  # fall back to the bare name (used for the "missing" message)

    return BioImage, BioImageViewer, bioio_tifffile, find_asset, mo, np, os, pd


@app.cell
def _(mo):
    mo.md("""
    # SAM 3 concept segmentation + anybioimage

    [SAM 3](https://docs.ultralytics.com/models/sam-3#key-innovations) adds
    **Promptable Concept Segmentation (PCS)**: give a *text phrase* and it segments
    **every** instance of that concept in one shot — no per-object clicking. That is
    the difference from the box/point flow in `sam_notebook.py`.

    This notebook runs SAM 3 with a text prompt, then overlays the returned masks as
    a label layer in the `BioImageViewer` widget.

    ## Before running

    - `pip install ultralytics` (>= 8.4 ships the SAM 3 predictors).
    - SAM 3 weights are **gated**: request access at
      [huggingface.co/facebook/sam3](https://huggingface.co/facebook/sam3),
      download `sam3.pt`, and place it next to this notebook.

    ## Caveats

    - **Compute:** SAM 3 is a large model. On CPU expect tens of seconds per image.
      For interactive use you want an NVIDIA GPU or a cloud runtime (Colab / Kaggle).
    - **Domain:** SAM 3 is trained on natural photos. On fluorescence microscopy a
      text prompt may segment poorly — treat this as a starting point, not a
      finished pipeline. Swap in your own image / prompt below.
    """)
    return


@app.cell
def _(mo):
    prompt = mo.ui.text(value="cell", label="Concept to segment")
    conf = mo.ui.slider(0.05, 0.9, value=0.25, step=0.05, label="Confidence")
    run = mo.ui.run_button(label="Run SAM 3")
    mo.vstack([prompt, conf, run])
    return conf, prompt, run


@app.cell
def _(BioImage, bioio_tifffile, find_asset, np):
    img = BioImage(find_asset("image.tif"), reader=bioio_tifffile.Reader)

    def _norm8(chan):
        lo, hi = np.percentile(chan, (1, 99))
        scaled = np.clip((chan.astype(np.float32) - lo) / max(hi - lo, 1e-6), 0, 1)
        return (scaled * 255).astype(np.uint8)

    # bioio .data is TCZYX (5D) or TCZYXS (6D, e.g. an RGB TIFF with a samples axis).
    # Build a contiguous (H, W, 3) uint8 image for SAM 3 regardless of the layout.
    arr = np.asarray(img.data)
    if arr.ndim == 6:  # TCZYXS -> (H, W, S)
        plane = arr[0, 0, 0]
    elif arr.ndim == 5:  # TCZYX -> (H, W, C)
        plane = np.moveaxis(arr[0, :, 0], 0, -1)
    else:
        plane = np.squeeze(arr)
        if plane.ndim == 2:
            plane = plane[..., None]

    n_ch = plane.shape[-1]
    if n_ch == 1:  # grayscale -> replicate to RGB
        gray = _norm8(plane[..., 0])
        rgb = np.dstack([gray, gray, gray])
    else:  # take the first 3 channels as R, G, B
        chans = [_norm8(plane[..., i]) for i in range(min(3, n_ch))]
        while len(chans) < 3:
            chans.append(chans[-1])
        rgb = np.dstack(chans)
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    return img, rgb


@app.cell
def _(BioImageViewer, img, mo):
    viewer = BioImageViewer()
    viewer.set_image(img)
    widget = mo.ui.anywidget(viewer)
    widget
    return viewer, widget


@app.cell
def _(conf, find_asset, mo, np, os, prompt, rgb, run, viewer):
    mo.stop(
        not run.value,
        mo.md("*Set a concept above and click **Run SAM 3** to segment.*"),
    )

    device = "cpu"
    try:
        import torch

        if torch.cuda.is_available():
            device = "cuda"
    except Exception:
        pass

    weights = find_asset("sam3.pt")
    if not os.path.exists(weights):
        result_view = mo.md(
            "**`sam3.pt` not found.** Download the gated weights from "
            "[huggingface.co/facebook/sam3](https://huggingface.co/facebook/sam3) "
            "and place `sam3.pt` next to this notebook, then click **Run SAM 3** again."
        )
    else:
        from ultralytics.models.sam import SAM3SemanticPredictor

        predictor = SAM3SemanticPredictor(
            overrides=dict(
                conf=conf.value,
                task="segment",
                mode="predict",
                model=weights,
                device=device,
                verbose=False,
            )
        )
        predictor.set_image(rgb)
        results = predictor(text=[prompt.value])
        if not isinstance(results, (list, tuple)):
            results = [results]

        # Combine every returned instance mask into a single uint16 label array.
        h, w = rgb.shape[:2]
        labels = np.zeros((h, w), dtype=np.uint16)
        n = 0
        for r in results:
            masks = getattr(r, "masks", None)
            if masks is None:
                continue
            for m in masks.data.cpu().numpy():
                mask_bool = m > 0.5
                if mask_bool.shape != (h, w):  # nearest-neighbor resize to image size
                    ys = (np.arange(h) * mask_bool.shape[0] / h).astype(int)
                    xs = (np.arange(w) * mask_bool.shape[1] / w).astype(int)
                    mask_bool = mask_bool[ys[:, None], xs]
                n += 1
                labels[mask_bool & (labels == 0)] = n

        if n:
            viewer.add_mask(labels, name=f"SAM3: {prompt.value}", opacity=0.5)
        result_view = mo.md(
            f"Segmented **{n}** instance(s) of *'{prompt.value}'* on `{device}`. "
            "The overlay appears in the viewer above."
        )

    result_view
    return


@app.cell
def _(mo, pd, widget):
    masks_data = widget.value.get("_masks_data", [])
    masks_df = (
        pd.DataFrame(
            [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "visible": m["visible"],
                    "opacity": m["opacity"],
                }
                for m in masks_data
            ]
        )
        if masks_data
        else pd.DataFrame(columns=["id", "name", "visible", "opacity"])
    )
    mo.vstack([mo.md("### Mask layers"), masks_df])
    return


if __name__ == "__main__":
    app.run()
