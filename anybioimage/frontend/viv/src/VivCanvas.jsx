// anybioimage/frontend/viv/src/VivCanvas.jsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { VivViewer, MultiscaleImageLayer } from '@hms-dbmi/viv';
import { openOmeZarr } from './zarr-source.js';
import { channelSettingsToVivProps, withTimeAndZ } from './channel-sync.js';
import { attachPixelInfo } from './pixel-info.js';

function useModelTrait(model, name) {
  const [value, setValue] = useState(() => model.get(name));
  useEffect(() => {
    const handler = () => setValue(model.get(name));
    model.on(`change:${name}`, handler);
    return () => model.off(`change:${name}`, handler);
  }, [model, name]);
  return value;
}

export function VivCanvas({ model }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const brightness = useModelTrait(model, 'image_brightness');
  const contrast = useModelTrait(model, 'image_contrast');
  const canvasHeight = useModelTrait(model, 'canvas_height') || 800;

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const deckRef = useRef(null);

  // Open the zarr store when _zarr_source changes.
  useEffect(() => {
    const url = zarrSource?.url;
    if (!url) {
      setSources(null);
      return;
    }
    let cancelled = false;
    openOmeZarr(url, zarrSource.headers || {})
      .then(({ sources }) => { if (!cancelled) setSources(sources); })
      .catch((e) => { if (!cancelled) { setError(String(e)); setSources(null); } });
    return () => { cancelled = true; };
  }, [zarrSource?.url]);

  const vivProps = useMemo(
    () => channelSettingsToVivProps(channelSettings || []),
    [channelSettings],
  );

  // Attach pixel-info hover once deck is mounted and sources are available.
  useEffect(() => {
    if (!deckRef.current || !sources) return;
    const selections = withTimeAndZ(vivProps.selections, currentT, currentZ);
    attachPixelInfo(model, deckRef.current.deck, () => sources, () => selections);
  }, [model, sources, currentT, currentZ, vivProps.selections]);

  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load zarr: {error}</div>;
  }
  if (!sources) {
    return <div style={{ padding: 12, color: '#666' }}>Loading…</div>;
  }

  const selections = withTimeAndZ(vivProps.selections, currentT, currentZ);
  const layer = new MultiscaleImageLayer({
    id: 'viv-image',
    loader: sources,
    selections,
    colors: vivProps.colors,
    contrastLimits: vivProps.contrastLimits,
    channelsVisible: vivProps.channelsVisible,
  });

  return (
    <div style={{ position: 'relative', width: '100%', height: canvasHeight }}>
      <VivViewer
        ref={deckRef}
        layerProps={[layer.props]}
        views={undefined /* Viv default OrthographicView */}
      />
      {vivProps.exceeded && (
        <div style={{ position: 'absolute', top: 8, right: 8, background: '#fbe9a0', padding: '4px 8px', fontSize: 12, borderRadius: 4 }}>
          More than 6 channels — extras hidden.
        </div>
      )}
    </div>
  );
}
