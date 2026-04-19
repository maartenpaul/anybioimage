// anybioimage/frontend/viewer/src/chrome/StatusBar.jsx
import React from 'react';
import { useModelTrait } from '../model/useModelTrait.js';

export function StatusBar({ model, hover }) {
  const t = useModelTrait(model, 'current_t') ?? 0;
  const z = useModelTrait(model, 'current_z') ?? 0;
  const dt = useModelTrait(model, 'dim_t') || 1;
  const dz = useModelTrait(model, 'dim_z') || 1;
  const parts = [];
  if (dt > 1) parts.push(`T ${t + 1}/${dt}`);
  if (dz > 1) parts.push(`Z ${z + 1}/${dz}`);
  return (
    <div className="status-bar">
      <span className="status-item dim-status">{parts.join(' · ')}</span>
      {hover && (
        <span className="status-item hover-status">
          x {hover.x}, y {hover.y}
          {hover.intensities && hover.intensities.map((v, i) =>
            v != null ? <React.Fragment key={i}> · ch{i}:{v}</React.Fragment> : null)}
        </span>
      )}
    </div>
  );
}
