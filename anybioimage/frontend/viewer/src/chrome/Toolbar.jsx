// anybioimage/frontend/viewer/src/chrome/Toolbar.jsx
import React from 'react';
import { useModelTrait } from '../model/useModelTrait.js';
import { ICONS, TOOL_ARIA, TOOL_SHORTCUT } from './icons.js';

function ToolButton({ model, mode }) {
  const current = useModelTrait(model, 'tool_mode');
  const active = current === mode;
  const aria = TOOL_ARIA[mode];
  const shortcut = TOOL_SHORTCUT[mode];
  const title = shortcut ? `${aria} (${shortcut})` : aria;
  return (
    <button
      className={'tool-btn' + (active ? ' active' : '')}
      aria-label={aria}
      aria-pressed={active}
      title={title}
      onClick={() => { model.set('tool_mode', mode); model.save_changes(); }}
    >{ICONS[mode]}</button>
  );
}

export function Toolbar({ model, onToggleLayers, panelOpen }) {
  return (
    <div className="toolbar">
      <div className="tool-group">
        <ToolButton model={model} mode="pan" />
        <ToolButton model={model} mode="select" />
      </div>
      <div className="toolbar-separator" />
      <div className="tool-group">
        <ToolButton model={model} mode="rect" />
        <ToolButton model={model} mode="polygon" />
        <ToolButton model={model} mode="point" />
      </div>
      <div className="toolbar-separator" />
      <button className="tool-btn"
              aria-label="Reset view"
              title="Reset view"
              onClick={() => model.send({ kind: 'reset-view' })}>{ICONS.reset}</button>
      <div className="toolbar-separator" />
      <button className={'layers-btn' + (panelOpen ? ' active' : '')}
              aria-label="Toggle layers panel"
              aria-pressed={panelOpen}
              title="Toggle layers panel"
              onClick={onToggleLayers}>
        <span>{ICONS.layers}</span><span> Layers</span>
      </button>
    </div>
  );
}
