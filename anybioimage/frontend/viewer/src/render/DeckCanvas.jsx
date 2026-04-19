// anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer, getDefaultInitialViewState } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { AnywidgetPixelSource } from './pixel-sources/anywidget-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { buildScaleBarLayer } from './layers/buildScaleBar.js';
import { useModelTrait } from '../model/useModelTrait.js';

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

export function DeckCanvas({ model, onHover, deckRef, sourcesRef, selectionsRef }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const pixelSourceMode = useModelTrait(model, '_pixel_source_mode');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const displayMode = useModelTrait(model, '_display_mode') || 'composite';
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  const pixelSizeUm = useModelTrait(model, 'pixel_size_um');
  const scaleBarVisible = useModelTrait(model, 'scale_bar_visible') !== false;
  const imageVisible = useModelTrait(model, 'image_visible') !== false;

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [viewState, setViewState] = useState(null);

  // Open the source whenever the mode or url changes.
  useEffect(() => {
    let cancelled = false;
    let activeAnywidgetSource = null;
    async function run() {
      setError(null);
      if (pixelSourceMode === 'chunk_bridge') {
        const shape = model.get('_image_shape') || null;
        const dtype = model.get('_image_dtype') || 'Uint16';
        if (!shape) { setSources(null); return; }
        activeAnywidgetSource = new AnywidgetPixelSource(model, {
          shape, dtype, tileSize: 512,
        });
        setSources([activeAnywidgetSource]);
      } else if (zarrSource?.url) {
        try {
          const { sources: srcs } = await openOmeZarr(zarrSource.url, zarrSource.headers || {});
          if (!cancelled) setSources(srcs);
        } catch (e) {
          if (!cancelled) { setError(String(e)); setSources(null); }
        }
      } else {
        setSources(null);
      }
    }
    run();
    return () => {
      cancelled = true;
      if (activeAnywidgetSource) activeAnywidgetSource.destroy();
    };
  }, [pixelSourceMode, zarrSource?.url]);

  // Reset view on new source.
  useEffect(() => {
    if (!sources || !sources.length) return;
    const vs = getDefaultInitialViewState(sources, { width, height }, 0);
    setViewState(vs);
  }, [sources, width, height]);

  // Expose refs for other parts of App (e.g. hover handler) without re-rendering on every change.
  useEffect(() => { if (sourcesRef) sourcesRef.current = sources; }, [sources, sourcesRef]);

  const imageLayerProps = useMemo(() => {
    if (!sources || !sources.length) return null;
    return buildImageLayerProps({
      sources, channels: channelSettings || [],
      currentT: currentT || 0, currentZ: currentZ || 0,
      displayMode, activeChannel,
    });
  }, [sources, channelSettings, currentT, currentZ, displayMode, activeChannel]);

  useEffect(() => {
    if (selectionsRef) selectionsRef.current = imageLayerProps?.selections ?? null;
  }, [imageLayerProps, selectionsRef]);

  // Listen for reset-view messages from the toolbar (added in Task 17).
  useEffect(() => {
    const handler = (content) => {
      if (!content || content.kind !== 'reset-view') return;
      if (!sources || !sources.length) return;
      const vs = getDefaultInitialViewState(sources, { width, height }, 0);
      setViewState(vs);
    };
    model.on('msg:custom', handler);
    return () => model.off('msg:custom', handler);
  }, [model, sources, width, height]);

  const layers = useMemo(() => {
    if (!imageLayerProps || !imageVisible) return [];
    const imageLayer = new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps });
    const out = [imageLayer];
    if (scaleBarVisible && pixelSizeUm) {
      out.push(buildScaleBarLayer({ pixelSizeUm, viewState, width, height }));
    }
    return out;
  }, [imageLayerProps, imageVisible, pixelSizeUm, scaleBarVisible, viewState, width, height]);

  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load image: {error}</div>;
  }

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {!sources ? (
        <div style={{ padding: 12, color: '#666' }}>Loading…</div>
      ) : (
        <DeckGL
          ref={deckRef}
          width={width}
          height={height}
          layers={layers}
          views={[new OrthographicView({ id: 'ortho', controller: true })]}
          viewState={viewState ? { ortho: viewState } : undefined}
          onViewStateChange={({ viewState: v }) => setViewState(v)}
          onHover={onHover}
          useDevicePixels={true}
          getCursor={({ isDragging }) => (isDragging ? 'grabbing' : 'crosshair')}
        />
      )}
    </div>
  );
}
