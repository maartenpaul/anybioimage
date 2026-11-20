// anybioimage/frontend/viewer/src/util/classifyLoadError.test.js
import { describe, it, expect } from 'vitest';
import { classifyLoadError } from './classifyLoadError.js';

const URL = 'https://s3.embl.de/bucket/img.ome.zarr';

describe('classifyLoadError', () => {
  it('diagnoses Firefox CORS/network failure as a CORS hint', () => {
    const err = new TypeError('NetworkError when attempting to fetch resource.');
    const out = classifyLoadError(err, URL);
    expect(out.title.toLowerCase()).toContain('cors');
    expect(out.detail).toContain(URL);
    expect(out.detail).toContain('canvas2d');
  });

  it('diagnoses Chrome "Failed to fetch" the same way', () => {
    const out = classifyLoadError(new TypeError('Failed to fetch'), URL);
    expect(out.title.toLowerCase()).toContain('cors');
  });

  it('diagnoses Safari "Load failed" the same way', () => {
    const out = classifyLoadError(new TypeError('Load failed'), URL);
    expect(out.title.toLowerCase()).toContain('cors');
  });

  it('passes through non-fetch errors verbatim', () => {
    const err = new Error('multiscales metadata missing');
    const out = classifyLoadError(err, URL);
    expect(out.title.toLowerCase()).not.toContain('cors');
    expect(out.detail).toContain('multiscales metadata missing');
  });

  it('does not misclassify a non-TypeError that mentions fetch', () => {
    const err = new Error('could not fetch chunk 0.0.0: 404');
    const out = classifyLoadError(err, URL);
    expect(out.title.toLowerCase()).not.toContain('cors');
  });
});
