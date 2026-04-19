// anybioimage/frontend/viv/src/VivCanvas.jsx
import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { PictureInPictureViewer } from '@hms-dbmi/viv';
import { openOmeZarr } from './zarr-source.js';
import { channelSettingsToVivProps, withTimeAndZ } from './channel-sync.js';

function useModelTrait(model, name) {
  const [value, setValue] = useState(() => model.get(name));
  useEffect(() => {
    const handler = () => setValue(model.get(name));
    model.on(`change:${name}`, handler);
    return () => model.off(`change:${name}`, handler);
  }, [model, name]);
  return value;
}

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
  }, [ref, fallback.height, fallback.width]);
  return size;
}

export function VivCanvas({ model, resetViewRef, sourcesRef }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const imageVisible = useModelTrait(model, 'image_visible');

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [resetToken, setResetToken] = useState(0);

  useEffect(() => {
    if (!resetViewRef) return;
    resetViewRef.fn = () => setResetToken((t) => t + 1);
    return () => { if (resetViewRef.fn) resetViewRef.fn = null; };
  }, [resetViewRef]);

  useEffect(() => {
    const url = zarrSource?.url;
    if (!url) {
      setSources(null);
      return;
    }
    let cancelled = false;
    setError(null);
    openOmeZarr(url, zarrSource.headers || {})
      .then(({ sources }) => {
        if (cancelled) return;
        setSources(sources);
        if (sourcesRef) sourcesRef.current = sources;
      })
      .catch((e) => { if (!cancelled) { setError(String(e)); setSources(null); } });
    return () => { cancelled = true; };
  }, [zarrSource?.url]);

  const vivProps = channelSettingsToVivProps(channelSettings || []);
  const selections = withTimeAndZ(vivProps.selections, currentT || 0, currentZ || 0);
  const showImage = imageVisible !== false;

  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load zarr: {error}</div>;
  }

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {!sources ? (
        <div style={{ padding: 12, color: '#666' }}>Loading OME-Zarr…</div>
      ) : showImage ? (
        <PictureInPictureViewer
          key={resetToken}
          loader={sources}
          selections={selections}
          colors={vivProps.colors}
          contrastLimits={vivProps.contrastLimits}
          channelsVisible={vivProps.channelsVisible}
          height={height}
          width={width}
        />
      ) : null}
      {vivProps.exceeded && (
        <div style={{ position: 'absolute', top: 8, right: 8, background: '#fbe9a0', padding: '4px 8px', fontSize: 12, borderRadius: 4, zIndex: 10 }}>
          More than 6 channels — extras hidden.
        </div>
      )}
    </div>
  );
}
