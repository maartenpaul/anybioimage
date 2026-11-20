// anybioimage/frontend/viewer/src/util/classifyLoadError.js
/**
 * Turn a raw zarr-load exception into a human-readable diagnosis.
 *
 * The Viv backend fetches OME-Zarr chunks directly from the browser, so it is
 * subject to the remote server's CORS policy. When the browser blocks a
 * cross-origin fetch it surfaces a generic `TypeError` ("NetworkError when
 * attempting to fetch resource." in Firefox, "Failed to fetch" in Chrome,
 * "Load failed" in Safari) with no detail — the spec deliberately hides whether
 * it was CORS, DNS, or offline. That bare message is useless to a notebook user,
 * so we detect the fetch-failure signature and explain the most likely cause.
 *
 * @param {unknown} err  the caught exception
 * @param {string}  url  the zarr URL we were loading
 * @returns {{ title: string, detail: string, raw: string }}
 */
export function classifyLoadError(err, url) {
  const raw = String(err);
  const msg = (err && err.message ? String(err.message) : raw).toLowerCase();
  const isFetchFailure =
    (err && err.name === 'TypeError') &&
    (msg.includes('networkerror') ||
      msg.includes('failed to fetch') ||
      msg.includes('load failed') ||
      msg.includes('fetch'));

  if (isFetchFailure) {
    let origin = '';
    try {
      origin = (typeof window !== 'undefined' && window.location && window.location.origin) || '';
    } catch {
      origin = '';
    }
    const originNote = origin ? ` This page's origin is ${origin}.` : '';
    return {
      title: 'Could not fetch the remote image (likely a CORS restriction).',
      detail:
        `The browser was blocked from fetching:\n${url}\n\n` +
        `The Viv backend loads zarr chunks directly in the browser, so the ` +
        `remote server must allow cross-origin requests from this notebook.` +
        `${originNote}\n\n` +
        `The server's metadata loaded server-side, so the URL is valid — only ` +
        `the browser fetch is blocked. Fixes:\n` +
        `  • Drop render_backend="viv" to use the default canvas2d backend ` +
        `(fetches through the kernel, no CORS).\n` +
        `  • Proxy the data through Jupyter (e.g. jupyter-server-proxy) so it's ` +
        `same-origin.\n` +
        `  • Ask the data host to allow this origin in the bucket's CORS config.`,
      raw,
    };
  }

  return {
    title: 'Failed to load image.',
    detail: raw,
    raw,
  };
}
