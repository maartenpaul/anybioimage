// anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx
import React from 'react';
import { MetadataSection } from './MetadataSection.jsx';
import { ImageSection } from './ImageSection.jsx';
import { MasksSection } from './MasksSection.jsx';
import { AnnotationsSection } from './AnnotationsSection.jsx';
import { ExportFooter } from './ExportFooter.jsx';

export function LayersPanel({ model }) {
  return (
    <div className="layers-panel open" style={{ width: 280, padding: 8, background: '#fafafa', overflowY: 'auto' }}>
      <MetadataSection model={model} />
      <ImageSection model={model} />
      <MasksSection model={model} />
      <AnnotationsSection model={model} />
      <div className="layer-item" style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
        <input
          type="checkbox"
          checked={!!model.get('sam_enabled')}
          onChange={(e) => { model.set('sam_enabled', e.target.checked); model.save_changes(); }}
        />
        <span>Use SAM on next rect / point</span>
      </div>
      <ExportFooter model={model} />
    </div>
  );
}
