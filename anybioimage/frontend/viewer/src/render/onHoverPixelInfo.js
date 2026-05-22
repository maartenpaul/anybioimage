/** Throttled hover handler that reads per-channel intensities. */
export function makeHoverHandler({ getSources, getSelections, setHover, intervalMs = 16 }) {
  let last = 0;
  let cachedRasters = null;
  let cachedKey = null;
  return async function onHover({ coordinate }) {
    if (!coordinate) { setHover(null); return; }
    const now = Date.now();
    if (now - last < intervalMs) return;
    last = now;
    const [x, y] = coordinate.map(Math.floor);
    const sources = getSources();
    const selections = getSelections();
    if (!sources || !sources.length) { setHover({ x, y, intensities: [] }); return; }
    const src = sources[0];
    const key = JSON.stringify(selections);
    if (cachedKey !== key) {
      cachedKey = key;
      cachedRasters = await Promise.all(selections.map((sel) =>
        src.getRaster({ selection: sel }).catch(() => null)));
    }
    const intensities = (cachedRasters || []).map((r) => {
      if (!r) return null;
      if (x < 0 || y < 0 || x >= r.width || y >= r.height) return null;
      return Number(r.data[y * r.width + x]);
    });
    setHover({ x, y, intensities });
  };
}
