// anybioimage/frontend/viewer/src/chrome/LayersPanel/MetadataSection.jsx
import React, { useState } from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

export function MetadataSection({ model }) {
  const [open, setOpen] = useState(false);
  const shape = useModelTrait(model, '_image_shape');
  const dtype = useModelTrait(model, '_image_dtype');
  const pixelSize = useModelTrait(model, 'pixel_size_um');
  const channels = useModelTrait(model, '_channel_settings') || [];
  if (!shape) return null;
  return (
    <div className="layer-item metadata-section" style={{ marginBottom: 8 }}>
      <button onClick={() => setOpen((v) => !v)} className="metadata-toggle" style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
        {open ? '▾' : '▸'} Metadata
      </button>
      {open && (
        <div className="metadata-body" style={{ padding: 4, fontSize: 12, color: '#333' }}>
          <div>Shape: T{shape.t} · C{shape.c} · Z{shape.z} · Y{shape.y} · X{shape.x}</div>
          <div>Dtype: {dtype}</div>
          <div>Pixel size: {pixelSize != null ? `${pixelSize.toFixed(4)} µm` : '—'}</div>
          <div>Channels: {channels.map((c) => c.name).join(', ')}</div>
        </div>
      )}
    </div>
  );
}
