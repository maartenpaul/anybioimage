// anybioimage/frontend/viewer/src/render/pixel-sources/bridge-source.js
// Build Viv PixelSources for a kernel-served zarr (`_zarr_source.mode === "bridge"`).
// One AnywidgetPixelSource per pyramid level; Viv's MultiscaleImageLayer reads
// tileSize/dtype from level 0 and calls getTile on whichever level it selects.
import { AnywidgetPixelSource } from './anywidget-source.js';

const DEFAULT_TILE = 512;
// Total JS-side tile budget shared by all levels of one image (tiles, not bytes;
// a 512² uint16 tile is 512 KB, so 256 tiles ≈ 128 MB worst case).
const TOTAL_CACHE_TILES = 256;
const MIN_CACHE_TILES_PER_LEVEL = 32;

/** Tile size that lines up with the store's yx chunks when they are square,
 *  a power of two, and within [256, 1024]; otherwise 512. */
export function pickTileSize(chunks, labels) {
  if (!Array.isArray(chunks) || !Array.isArray(labels)) return DEFAULT_TILE;
  const cy = chunks[labels.indexOf('y')];
  const cx = chunks[labels.indexOf('x')];
  const pow2 = Number.isInteger(cy) && cy > 0 && (cy & (cy - 1)) === 0;
  if (cy === cx && pow2 && cy >= 256 && cy <= 1024) return cy;
  return DEFAULT_TILE;
}

/** Per-level LRU cap so the whole pyramid stays within TOTAL_CACHE_TILES. */
export function cacheSizePerLevel(nLevels) {
  const n = Math.max(1, nLevels | 0);
  return Math.max(MIN_CACHE_TILES_PER_LEVEL, Math.floor(TOTAL_CACHE_TILES / n));
}

export function openBridge(model, zarrSource) {
  const levels = Array.isArray(zarrSource?.levels) ? zarrSource.levels : [];
  const labels = zarrSource?.labels || ['t', 'c', 'z', 'y', 'x'];
  const dtype = AnywidgetPixelSource.dtypeFromPython(zarrSource?.dtype);
  const tileSize = pickTileSize(levels[0]?.chunks, labels);
  const cacheSize = cacheSizePerLevel(levels.length);
  return levels.map((lvl, level) => new AnywidgetPixelSource(model, {
    shape: lvl.shape, dtype, tileSize, level, labels, cacheSize,
  }));
}
