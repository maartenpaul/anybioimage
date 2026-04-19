// anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer, getDefaultInitialViewState } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { AnywidgetPixelSource } from './pixel-sources/anywidget-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { buildScaleBarLayer } from './layers/buildScaleBar.js';
import { annotationsToLayers } from './layers/annotationsToLayers.js';
import { buildMaskLayers } from './layers/buildMaskLayers.js';
import { useModelTrait } from '../model/useModelTrait.js';
import { trace } from '../util/perf.js';

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

export function DeckCanvas({ model, onHover, controller, maskBridge, deckRef, sourcesRef, selectionsRef }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const pixelSourceMode = useModelTrait(model, '_pixel_source_mode');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const displayMode = useModelTrait(model, '_display_mode');
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  const imageShape = useModelTrait(model, '_image_shape');
  const imageDtype = useModelTrait(model, '_image_dtype');
  const pixelSizeUm = useModelTrait(model, 'pixel_size_um');
  const scaleBarVisible = useModelTrait(model, 'scale_bar_visible') !== false;
  const imageVisible = useModelTrait(model, 'image_visible') !== false;
  const annotations = useModelTrait(model, '_annotations') || [];
  const selectedId = useModelTrait(model, 'selected_annotation_id') || '';
  const toolMode = useModelTrait(model, 'tool_mode') || 'pan';
  const masks = useModelTrait(model, '_masks_data') || [];

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [viewState, setViewState] = useState(null);
  const [previewTick, setPreviewTick] = useState(0);
  const [maskTick, setMaskTick] = useState(0);

  useEffect(() => {
    if (!controller) return;
    return controller.onPreviewChange(() => setPreviewTick((t) => t + 1));
  }, [controller]);

  useEffect(() => {
    if (!maskBridge) return;
    const unsubs = masks.map((m) => maskBridge.subscribe(m.id, () => setMaskTick((t) => t + 1)));
    return () => { for (const u of unsubs) u(); };
  }, [maskBridge, masks]);

  useEffect(() => {
    let cancelled = false;
    let activeAnywidgetSource = null;
    async function run() {
      setError(null);
      if (pixelSourceMode === 'chunk_bridge') {
        if (!imageShape || imageShape.length !== 5) { setSources(null); return; }
        activeAnywidgetSource = new AnywidgetPixelSource(model, {
          shape: imageShape, dtype: imageDtype || 'Uint16', tileSize: 512,
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
  }, [pixelSourceMode, zarrSource?.url, imageShape, imageDtype]);

  useEffect(() => {
    if (!sources || !sources.length) return;
    const vs = getDefaultInitialViewState(sources, { width, height }, 0);
    setViewState(vs);
  }, [sources, width, height]);

  useEffect(() => { if (sourcesRef) sourcesRef.current = sources; }, [sources, sourcesRef]);

  const imageLayerProps = useMemo(() => {
    if (!sources || !sources.length) return null;
    return buildImageLayerProps({
      sources, channels: channelSettings || [],
      currentT: currentT || 0, currentZ: currentZ || 0,
      displayMode, activeChannel,
    });
  }, [sources, channelSettings, currentT, currentZ, displayMode, activeChannel]);

  // _render_ready: flipped True once we have both a valid image-layer prop set
  // AND a non-null viewState (the canvas has rendered a frame). Fixtures block
  // on this trait via wait_for_ready(). Flip-once semantics — don't churn it
  // on every re-render.
  useEffect(() => {
    if (imageLayerProps && viewState && !model.get('_render_ready')) {
      model.set('_render_ready', true);
      model.save_changes();
    }
  }, [imageLayerProps, viewState, model]);

  useEffect(() => {
    if (selectionsRef) selectionsRef.current = imageLayerProps?.selections ?? null;
  }, [imageLayerProps, selectionsRef]);

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

  const annotationLayers = useMemo(
    () => annotationsToLayers({
      annotations, currentT: currentT || 0, currentZ: currentZ || 0, selectedId,
    }),
    [annotations, currentT, currentZ, selectedId]);

  const maskLayers = useMemo(
    () => (maskBridge ? buildMaskLayers({ masks, bridge: maskBridge }) : []),
    [masks, maskBridge, maskTick]); // eslint-disable-line react-hooks/exhaustive-deps

  const previewLayer = useMemo(
    () => (controller ? controller.getPreviewLayer() : null),
    [controller, previewTick, toolMode]);

  const layers = useMemo(() => trace('layers:build', () => {
    const out = [];
    if (imageLayerProps && imageVisible) {
      out.push(new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps }));
    }
    for (const l of maskLayers) out.push(l);
    for (const l of annotationLayers) out.push(l);
    if (previewLayer) out.push(previewLayer);
    if (scaleBarVisible && pixelSizeUm) {
      out.push(buildScaleBarLayer({ pixelSizeUm, viewState, width, height }));
    }
    return out;
  }), [imageLayerProps, imageVisible, maskLayers, annotationLayers, previewLayer,
      pixelSizeUm, scaleBarVisible, viewState, width, height]);

  function imagePixelFor(info) {
    const coord = info?.coordinate;
    if (!coord) return null;
    return { x: coord[0], y: coord[1] };
  }

  function pickObject(event) {
    const deck = deckRef?.current?.deck;
    if (!deck || !event) return null;
    const picked = deck.pickObject({
      x: event.screenX ?? event._screenX ?? 0,
      y: event.screenY ?? event._screenY ?? 0,
      radius: 4,
    });
    if (!picked) return null;
    const id = picked.object?.id;
    const sourceAnnotation = id ? annotations.find((a) => a.id === id) : null;
    return { layer: picked.layer, object: picked.object, sourceAnnotation };
  }

  // Inject pickObject into the interaction controller's tool context
  // [spec §5.1]. `pickObject` is a new closure every render (it captures
  // `annotations` and `deckRef`), but setContext just merges into _ctx so
  // the cost is one object spread per render.
  useEffect(() => {
    if (!controller) return;
    controller.setContext({ pickObject });
  });  // no dep list — runs every render, matches the closure's capture window

  function onClick(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    const ev = { ...pt, screenX: info.x, screenY: info.y, _picked: pickObject(info) };
    controller.handlePointerEvent('down', ev);
    controller.handlePointerEvent('up', ev);
  }

  function onDragStart(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('down', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDrag(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('move', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDragEnd(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('up', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDblClick(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    const tool = controller.activeTool;
    if (tool.onDoubleClick) tool.onDoubleClick(pt, { model, controller, pickObject });
  }

  const viewController = toolMode === 'pan' || toolMode === 'select';

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
          views={[new OrthographicView({ id: 'ortho', controller: viewController })]}
          viewState={viewState ? { ortho: viewState } : undefined}
          onViewStateChange={({ viewState: v }) => setViewState(v)}
          onHover={onHover}
          onClick={onClick}
          onDragStart={onDragStart}
          onDrag={onDrag}
          onDragEnd={onDragEnd}
          onDblClick={onDblClick}
          useDevicePixels={true}
          getCursor={({ isDragging }) =>
            isDragging ? 'grabbing' : (controller?.cursor || 'crosshair')
          }
        />
      )}
    </div>
  );
}
