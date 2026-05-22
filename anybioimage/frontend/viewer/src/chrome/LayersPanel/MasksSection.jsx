// anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.jsx
import React from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

function update(model, id, changes) {
  model.send({ kind: 'mask_update', id, ...changes });
}

function remove(model, id) {
  model.send({ kind: 'mask_delete', id });
}

export function MasksSection({ model }) {
  const masks = useModelTrait(model, '_masks_data') || [];
  return (
    <div className="layers-section" style={{ padding: '4px 8px' }}>
      <div className="layer-header" style={{ padding: '6px 0', fontSize: 11, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>
        Masks ({masks.length})
      </div>
      {masks.length === 0 && (
        <div style={{ color: '#999', fontSize: 12, padding: '4px 0' }}>
          No masks — call <code>viewer.add_mask(labels)</code>.
        </div>
      )}
      {masks.map((m) => (
        <div key={m.id} className="layer-item mask-layer"
             style={{ display: 'flex', flexDirection: 'column', padding: '6px 4px', borderRadius: 4, background: '#fff', marginBottom: 4, gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={() => update(model, m.id, { visible: !m.visible })}
              style={{ background: 'none', border: 'none', cursor: 'pointer',
                       color: m.visible ? '#0d6efd' : '#999' }}
              title={m.visible ? 'Hide' : 'Show'}
            >{m.visible ? '👁' : '⊘'}</button>
            <input
              type="color"
              className="color-swatch"
              value={m.color || '#ff0000'}
              onChange={(e) => update(model, m.id, { color: e.target.value })}
              style={{ width: 20, height: 20, padding: 0, border: '1px solid #ccc', borderRadius: 3 }}
            />
            <span style={{ flex: 1, fontSize: 13 }}>{m.name}</span>
            <button
              onClick={() => remove(model, m.id)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#c33' }}
              title="Delete"
            >🗑</button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11, color: '#888', width: 50 }}>Opacity</span>
            <input
              type="range" min={0} max={1} step={0.05}
              value={m.opacity ?? 0.5}
              onChange={(e) => update(model, m.id, { opacity: parseFloat(e.target.value) })}
              style={{ flex: 1 }}
            />
            <span style={{ fontSize: 11, color: '#888', width: 30, textAlign: 'right' }}>
              {(m.opacity ?? 0.5).toFixed(2)}
            </span>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#555' }}>
            <input
              type="checkbox"
              checked={!!m.contours}
              onChange={(e) => update(model, m.id, { contours: e.target.checked })}
            />
            <span>Contours only</span>
          </label>
        </div>
      ))}
    </div>
  );
}
