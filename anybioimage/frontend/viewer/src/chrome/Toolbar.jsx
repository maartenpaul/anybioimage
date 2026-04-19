// anybioimage/frontend/viewer/src/chrome/Toolbar.jsx
import React from 'react';
import { useModelTrait } from '../model/useModelTrait.js';

const ICONS = {
  pan: 'P', select: 'V', reset: '↺', layers: '☰',
  // Phase 2 tools show but are disabled until implemented.
  rect: '▭', polygon: '⬡', point: '•',
  line: '／', areaMeasure: '△', lineProfile: '∼',
};

function ToolButton({ model, mode, label, disabled }) {
  const current = useModelTrait(model, 'tool_mode');
  const active = current === mode;
  return (
    <button
      className={'tool-btn' + (active ? ' active' : '')}
      disabled={disabled}
      title={label}
      onClick={() => { model.set('tool_mode', mode); model.save_changes(); }}
    >{ICONS[mode] || mode}</button>
  );
}

export function Toolbar({ model, onToggleLayers, panelOpen }) {
  const phase2Disabled = true;   // rect/polygon/point/measure land in Phase 2
  return (
    <div className="toolbar">
      <div className="tool-group">
        <ToolButton model={model} mode="pan" label="Pan (P)" />
        <ToolButton model={model} mode="select" label="Select (V)" />
      </div>
      <div className="toolbar-separator" />
      <div className="tool-group">
        <ToolButton model={model} mode="rect" label="Rectangle (R)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="polygon" label="Polygon (G)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="point" label="Point (O)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="line" label="Line (L)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="areaMeasure" label="Area measure (M)" disabled={phase2Disabled} />
      </div>
      <div className="toolbar-separator" />
      <button className="tool-btn" title="Reset view"
              onClick={() => model.send({ kind: 'reset-view' })}>{ICONS.reset}</button>
      <div className="toolbar-separator" />
      <button className={'layers-btn' + (panelOpen ? ' active' : '')} onClick={onToggleLayers}>
        <span>{ICONS.layers}</span><span> Layers</span>
      </button>
    </div>
  );
}
