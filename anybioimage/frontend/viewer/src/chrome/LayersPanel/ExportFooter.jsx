// anybioimage/frontend/viewer/src/chrome/LayersPanel/ExportFooter.jsx
import React from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

export function ExportFooter({ model }) {
  const scaleBarVisible = useModelTrait(model, 'scale_bar_visible') !== false;
  const pixelSizeUm = useModelTrait(model, 'pixel_size_um');
  return (
    <div className="layers-footer" style={{ borderTop: '1px solid #e0e0e0', marginTop: 8, paddingTop: 8 }}>
      {pixelSizeUm != null && (
        <label className="layers-footer-toggle" style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={scaleBarVisible}
            onChange={(e) => { model.set('scale_bar_visible', e.target.checked); model.save_changes(); }} />
          Scale bar
        </label>
      )}
      {/* Annotation export buttons land in Phase 3 */}
    </div>
  );
}
