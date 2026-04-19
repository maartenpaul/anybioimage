// anybioimage/frontend/viv/src/zarr-source.js
import { loadOmeZarr } from '@hms-dbmi/viv';

/**
 * Open an OME-Zarr store at `url` and return a list of ZarrPixelSource
 * instances — one per multiscale level — plus the store's root attrs.
 *
 * Uses Viv's own loader (built on zarr.js's HTTPStore), which fetches chunks
 * directly from the browser. No kernel round-trip for tile data.
 *
 * Viv's `loadOmeZarr` requires `options.type === "multiscales"` and will
 * throw otherwise; we always pass it.
 */
export async function openOmeZarr(url, headers = {}) {
  const options = { type: 'multiscales' };
  if (headers && Object.keys(headers).length > 0) {
    options.fetchOptions = { headers };
  }
  const { data, metadata } = await loadOmeZarr(url, options);
  const ome = metadata?.ome ?? metadata ?? {};
  const labels = data[0]?.labels ?? [];
  return { sources: data, labels, ome };
}
