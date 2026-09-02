// anybioimage/frontend/viewer/src/render/VivCanvas.jsx
// Slim Viv canvas: remote OME-Zarr only. Derived from the unified viewer's
// DeckCanvas.jsx with masks/annotations/tools stripped (deferred per spec §4).
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer, getDefaultInitialViewState } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { openBridge } from './pixel-sources/bridge-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { useModelTrait } from '../model/useModelTrait.js';
import { classifyLoadError } from '../util/classifyLoadError.js';

function useContainerSize(ref, fallback = { width: 800, height: 600 }) {
  const [size, setSize] = useState(fallback);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      setSize({
        width: Math.max(1, Math.floor(rect.width)) || fallback.width,
        height: Math.max(1, Math.floor(rect.height)) || fallback.height,
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, fallback.width, fallback.height]);
  return size;
}

export function VivCanvas({ model }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const imageVisible = useModelTrait(model, 'image_visible') !== false;

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);
  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [viewState, setViewState] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let bridgeSources = null;
    async function run() {
      setError(null);
      const mode = zarrSource?.mode;
      if (!mode) { setSources(null); return; }
      try {
        let srcs;
        if (mode === 'bridge') {
          bridgeSources = openBridge(model, zarrSource);
          srcs = bridgeSources;
        } else {
          ({ sources: srcs } = await openOmeZarr(zarrSource.url, zarrSource.headers || {}));
        }
        if (!cancelled) setSources(srcs);
      } catch (e) {
        if (!cancelled) { setError(classifyLoadError(e, zarrSource.url || '(kernel bridge)')); setSources(null); }
      }
    }
    run();
    return () => {
      cancelled = true;
      if (bridgeSources) bridgeSources.forEach((s) => s.destroy());
    };
  }, [zarrSource, model]);

  useEffect(() => {
    if (!sources || !sources.length) return;
    setViewState(getDefaultInitialViewState(sources, { width, height }, 0));
    // Intentionally not depending on width/height: don't reset the user's
    // pan/zoom on container resize.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sources]);

  const imageLayerProps = useMemo(() => {
    if (!sources || !sources.length) return null;
    return buildImageLayerProps({
      sources,
      channels: channelSettings || [],
      currentT: currentT || 0,
      currentZ: currentZ || 0,
    });
  }, [sources, channelSettings, currentT, currentZ]);

  // Flip-once readiness flag for tests/fixtures.
  useEffect(() => {
    if (imageLayerProps && viewState && !model.get('_render_ready')) {
      model.set('_render_ready', true);
      model.save_changes();
    }
  }, [imageLayerProps, viewState, model]);

  const layers = useMemo(() => {
    if (!imageLayerProps || !imageVisible) return [];
    return [new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps })];
  }, [imageLayerProps, imageVisible]);

  if (!zarrSource?.mode) return null;
  if (error) {
    return (
      <div style={{ color: '#b00', padding: 12 }}>
        <strong>{error.title}</strong>
        <pre style={{ whiteSpace: 'pre-wrap', margin: '8px 0 0', font: 'inherit' }}>{error.detail}</pre>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {!sources ? (
        <div style={{ padding: 12, color: '#666' }}>Loading…</div>
      ) : (
        <DeckGL
          width={width}
          height={height}
          layers={layers}
          views={[new OrthographicView({ id: 'ortho', controller: true })]}
          viewState={viewState ? { ortho: viewState } : undefined}
          onViewStateChange={({ viewState: v }) => setViewState(v)}
          useDevicePixels={true}
          getCursor={({ isDragging }) => (isDragging ? 'grabbing' : 'grab')}
        />
      )}
    </div>
  );
}
