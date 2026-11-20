"""Viv backend: pre-built esbuild bundle (browser-direct zarr fetch + WebGL2)."""
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def get_esm() -> str:
    bundle = files("anybioimage") / "frontend" / "viewer" / "dist" / "viewer-bundle.js"
    try:
        return bundle.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise RuntimeError(
            "Viv bundle not found. Build it with: "
            "cd anybioimage/frontend/viewer && npm install && npm run build"
        ) from e
