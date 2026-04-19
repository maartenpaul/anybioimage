// anybioimage/frontend/viv/src/pixel-info.js

/**
 * Throttle `fn` so it fires at most once per `wait` ms, with a trailing call.
 */
function throttle(fn, wait) {
  let last = 0;
  let timer = null;
  let pendingArgs = null;
  return function throttled(...args) {
    const now = Date.now();
    pendingArgs = args;
    if (now - last >= wait) {
      last = now;
      fn(...args);
      pendingArgs = null;
    } else if (!timer) {
      timer = setTimeout(() => {
        last = Date.now();
        timer = null;
        if (pendingArgs) fn(...pendingArgs);
        pendingArgs = null;
      }, wait - (now - last));
    }
  };
}

export function attachPixelInfo(model, deckInstance, getSources, getSelections) {
  const emit = throttle((info) => {
    model.set('_pixel_info', info);
    model.save_changes();
  }, 120);

  deckInstance.setProps({
    onHover: async ({ coordinate }) => {
      if (!coordinate) {
        emit(null);
        return;
      }
      const [x, y] = coordinate.map(Math.round);
      const sources = getSources();
      const selections = getSelections();
      if (!sources || sources.length === 0) return;
      const src = sources[0];
      const intensities = [];
      for (const sel of selections) {
        try {
          const { data } = await src.getRaster({ selection: sel });
          const idx = y * src.shape[src.labels.indexOf('x')] + x;
          intensities.push(Number(data[idx]));
        } catch {
          intensities.push(null);
        }
      }
      emit({ x, y, intensities });
    },
  });
}
