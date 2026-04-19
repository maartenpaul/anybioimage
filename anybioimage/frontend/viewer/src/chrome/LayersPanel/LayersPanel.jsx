// anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx
import React from 'react';
import { MetadataSection } from './MetadataSection.jsx';
import { ImageSection } from './ImageSection.jsx';
import { ExportFooter } from './ExportFooter.jsx';

export function LayersPanel({ model }) {
  return (
    <div className="layers-panel open" style={{ width: 280, padding: 8, background: '#fafafa', overflowY: 'auto' }}>
      <MetadataSection model={model} />
      <ImageSection model={model} />
      <div className="layer-item section-placeholder" style={{ color: '#999', fontStyle: 'italic', padding: '8px 4px' }}>Masks (Phase 2)</div>
      <div className="layer-item section-placeholder" style={{ color: '#999', fontStyle: 'italic', padding: '8px 4px' }}>Annotations (Phase 2)</div>
      <ExportFooter model={model} />
    </div>
  );
}
