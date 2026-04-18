// anybioimage/frontend/viv/src/zarr-source.js
import * as zarr from 'zarrita';
import { ZarrPixelSource } from '@hms-dbmi/viv';

/**
 * Open an OME-Zarr store at `url` and return a list of ZarrPixelSource
 * instances — one per multiscale level.
 */
export async function openOmeZarr(url, headers = {}) {
  const store = new zarr.FetchStore(url, { overrides: { headers } });
  const root = await zarr.open(store, { kind: 'group' });
  const attrs = root.attrs ?? {};
  const ome = attrs.ome ?? attrs;
  const multiscales = ome.multiscales;
  if (!multiscales || multiscales.length === 0) {
    throw new Error(`No OME-Zarr multiscales at ${url}`);
  }
  const ms = multiscales[0];
  const axes = ms.axes.map(a => a.name.toLowerCase());
  const labels = axes;

  const sources = [];
  for (const dataset of ms.datasets) {
    const arr = await zarr.open(root.resolve(dataset.path), { kind: 'array' });
    sources.push(new ZarrPixelSource(arr, { labels, tileSize: 512 }));
  }
  return { sources, labels, ome };
}
