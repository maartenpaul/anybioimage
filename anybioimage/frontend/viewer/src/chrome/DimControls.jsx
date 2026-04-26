// anybioimage/frontend/viewer/src/chrome/DimControls.jsx
import React, { useEffect, useState } from 'react';
import { useModelTrait } from '../model/useModelTrait.js';
import { ICONS } from './icons.js';

function useLivePlay(model, key, max, speed = 200) {
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const next = ((model.get(key) ?? 0) + 1) % max;
      model.set(key, next); model.save_changes();
    }, speed);
    return () => clearInterval(id);
  }, [playing, model, key, max, speed]);
  return [playing, setPlaying];
}

function PlayButton({ model, traitKey, max }) {
  const [playing, setPlaying] = useLivePlay(model, traitKey, max);
  const label = playing ? 'Pause' : 'Play';
  return (
    <button
      className="play-btn"
      aria-label={label}
      aria-pressed={playing}
      title={label}
      onClick={() => setPlaying(!playing)}>
      {playing ? ICONS.pause : ICONS.play}
    </button>
  );
}

function DimSlider({ model, label, traitKey, max, showPlay = false }) {
  const value = useModelTrait(model, traitKey) ?? 0;
  if (max <= 1) return null;
  return (
    <div className="dim-slider-wrapper">
      <span className="dim-label">{label}</span>
      {showPlay && <PlayButton model={model} traitKey={traitKey} max={max} />}
      <input className="dim-slider" type="range" min="0" max={max - 1} value={value}
        aria-label={`${label} index`}
        onChange={(e) => { model.set(traitKey, parseInt(e.target.value)); model.save_changes(); }} />
      <span className="dim-value">{value}/{max}</span>
    </div>
  );
}

function Selector({ model, label, listKey, currentKey }) {
  const items = useModelTrait(model, listKey) || [];
  const current = useModelTrait(model, currentKey);
  if (items.length === 0) return null;
  return (
    <div className="scene-selector-wrapper">
      <span className="dim-label">{label}</span>
      <select className="scene-select" value={current || ''}
        aria-label={label}
        onChange={(e) => { model.set(currentKey, e.target.value); model.save_changes(); }}>
        {items.map((i) => <option key={i} value={i}>{i}</option>)}
      </select>
    </div>
  );
}

export function DimControls({ model }) {
  const dimT = useModelTrait(model, 'dim_t') || 1;
  const dimZ = useModelTrait(model, 'dim_z') || 1;
  const scenes = useModelTrait(model, 'scenes') || [];
  const wells = useModelTrait(model, 'plate_wells') || [];
  const fovs = useModelTrait(model, 'plate_fovs') || [];
  const hasAny = dimT > 1 || dimZ > 1 || scenes.length > 1 || wells.length > 0;
  if (!hasAny) return null;
  return (
    <div className="dimension-controls">
      <Selector model={model} label="Well" listKey="plate_wells" currentKey="current_well" />
      <Selector model={model} label="FOV" listKey="plate_fovs" currentKey="current_fov" />
      {scenes.length > 1 && <Selector model={model} label="Scene" listKey="scenes" currentKey="current_scene" />}
      <DimSlider model={model} label="T" traitKey="current_t" max={dimT} showPlay />
      <DimSlider model={model} label="Z" traitKey="current_z" max={dimZ} />
    </div>
  );
}
