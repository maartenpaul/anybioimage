// anybioimage/frontend/viewer/src/chrome/LayersPanel/AnnotationsSection.jsx
import React, { useState } from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

const KINDS = [
  { kind: 'rect', label: 'Rectangles' },
  { kind: 'polygon', label: 'Polygons' },
  { kind: 'point', label: 'Points' },
];

function setAnnotations(model, next) {
  model.set('_annotations', next);
  model.save_changes();
}

function toggleKindVisibility(model, annotations, kind, visible) {
  setAnnotations(model, annotations.map((a) =>
    a.kind === kind ? { ...a, visible } : a
  ));
}

function clearKind(model, annotations, kind) {
  setAnnotations(model, annotations.filter((a) => a.kind !== kind));
}

function toggleOne(model, annotations, id) {
  setAnnotations(model, annotations.map((a) =>
    a.id === id ? { ...a, visible: !a.visible } : a
  ));
}

function removeOne(model, annotations, id) {
  setAnnotations(model, annotations.filter((a) => a.id !== id));
}

export function AnnotationsSection({ model }) {
  const annotations = useModelTrait(model, '_annotations') || [];
  const [expanded, setExpanded] = useState({});

  const byKind = Object.fromEntries(
    KINDS.map(({ kind }) => [kind, annotations.filter((a) => a.kind === kind)])
  );

  return (
    <div className="layers-section" style={{ padding: '4px 8px' }}>
      <div className="layer-header" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 0', fontSize: 11, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>
        <span>Annotations</span>
      </div>
      {KINDS.map(({ kind, label }) => {
        const items = byKind[kind];
        const anyVisible = items.some((a) => a.visible);
        const isExpanded = expanded[kind];
        return (
          <div key={kind}>
            <div className="layer-item" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
              <button
                className="layer-toggle"
                onClick={() => setExpanded({ ...expanded, [kind]: !isExpanded })}
                style={{ width: 16, background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}
                title={isExpanded ? 'Collapse' : 'Expand'}
              >{isExpanded ? '▾' : '▸'}</button>
              <span style={{ flex: 1, fontSize: 13 }}>{label} ({items.length})</span>
              <button
                className="layer-toggle"
                onClick={() => toggleKindVisibility(model, annotations, kind, !anyVisible)}
                title={anyVisible ? 'Hide all' : 'Show all'}
                style={{ background: 'none', border: 'none', cursor: 'pointer',
                         color: anyVisible ? '#0d6efd' : '#999' }}
              >{anyVisible ? '👁' : '⊘'}</button>
              <button
                className="layer-action-btn"
                onClick={() => clearKind(model, annotations, kind)}
                disabled={items.length === 0}
                title="Delete all"
                style={{ background: 'none', border: 'none', cursor: 'pointer',
                         color: items.length ? '#c33' : '#ccc' }}
              >🗑</button>
            </div>
            {isExpanded && items.map((a) => (
              <div key={a.id} className="layer-item sub-item" style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 28, fontSize: 12 }}>
                <span style={{ flex: 1, fontFamily: 'monospace', color: '#555' }}>{a.id}</span>
                <button
                  onClick={() => toggleOne(model, annotations, a.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer',
                           color: a.visible ? '#0d6efd' : '#999' }}
                  title={a.visible ? 'Hide' : 'Show'}
                >{a.visible ? '👁' : '⊘'}</button>
                <button
                  onClick={() => removeOne(model, annotations, a.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#c33' }}
                  title="Delete"
                >🗑</button>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
