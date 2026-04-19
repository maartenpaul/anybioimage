// anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx
import React from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';
import { listLuts } from '../../render/luts/index.js';

function setChannel(model, idx, patch) {
  const settings = [...(model.get('_channel_settings') || [])];
  settings[idx] = { ...settings[idx], ...patch };
  model.set('_channel_settings', settings);
  model.save_changes();
}

function ImageRow({ model }) {
  const visible = useModelTrait(model, 'image_visible') !== false;
  const displayMode = useModelTrait(model, '_display_mode') || 'composite';
  return (
    <div className="layer-item image-row" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
      <button className={'layer-toggle' + (visible ? ' visible' : '')}
        onClick={() => { model.set('image_visible', !visible); model.save_changes(); }}
        style={{ background: 'none', border: 'none', cursor: 'pointer' }}
        title={visible ? 'Hide image' : 'Show image'}>
        {visible ? '👁' : '⊘'}
      </button>
      <span style={{ flex: 1 }}>Image</span>
      <select value={displayMode}
        onChange={(e) => { model.set('_display_mode', e.target.value); model.save_changes(); }}>
        <option value="composite">Composite</option>
        <option value="single">Single</option>
      </select>
    </div>
  );
}

function ChannelRow({ model, ch, idx, active, onActivate }) {
  const luts = listLuts();
  return (
    <>
      <div className={'layer-item channel-layer-item' + (active ? ' active-channel' : '')}
           onClick={onActivate}
           style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0',
                    background: active ? '#eef5ff' : 'transparent', cursor: 'pointer' }}>
        <button className={'layer-toggle' + (ch.visible ? ' visible' : '')}
          onClick={(e) => { e.stopPropagation(); setChannel(model, idx, { visible: !ch.visible }); }}
          style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
          {ch.visible ? '👁' : '⊘'}
        </button>
        <span className="channel-name" style={{ flex: 1, fontSize: 12 }}>{ch.name || `Ch ${idx}`}</span>

        <select value={ch.color_kind || 'solid'}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setChannel(model, idx, { color_kind: e.target.value })}
          style={{ fontSize: 11 }}>
          <option value="solid">Solid</option>
          <option value="lut">LUT</option>
        </select>

        {ch.color_kind === 'lut' ? (
          <select value={ch.lut || 'viridis'}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { lut: e.target.value })}
            style={{ fontSize: 11 }}>
            {luts.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        ) : (
          <input type="color" value={ch.color || '#ffffff'}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { color: e.target.value })}
            style={{ width: 24, height: 20, border: 'none', padding: 0 }} />
        )}

        <button className="auto-contrast-btn"
          onClick={(e) => {
            e.stopPropagation();
            model.send({ kind: 'auto-contrast', channelIndex: idx });
          }}
          style={{ fontSize: 11, padding: '2px 6px' }}>Auto</button>
      </div>

      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Min</span>
        <input type="range" min="0" max="100" value={Math.round((ch.min ?? 0) * 100)}
          onChange={(e) => setChannel(model, idx, { min: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <span className="slider-value" style={{ width: 32, textAlign: 'right' }}>{Math.round((ch.min ?? 0) * 100)}%</span>
      </div>
      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Max</span>
        <input type="range" min="0" max="100" value={Math.round((ch.max ?? 1) * 100)}
          onChange={(e) => setChannel(model, idx, { max: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <span className="slider-value" style={{ width: 32, textAlign: 'right' }}>{Math.round((ch.max ?? 1) * 100)}%</span>
      </div>
      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Gamma</span>
        <input type="range" min="10" max="500" value={Math.round((ch.gamma ?? 1) * 100)}
          onChange={(e) => setChannel(model, idx, { gamma: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <span className="slider-value" style={{ width: 32, textAlign: 'right' }}>{(ch.gamma ?? 1).toFixed(2)}</span>
      </div>
    </>
  );
}

export function ImageSection({ model }) {
  const channels = useModelTrait(model, '_channel_settings') || [];
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  return (
    <>
      <ImageRow model={model} />
      {channels.map((ch, idx) => (
        <ChannelRow key={idx} model={model} ch={ch} idx={idx}
          active={idx === activeChannel}
          onActivate={() => { model.set('current_c', idx); model.save_changes(); }} />
      ))}
    </>
  );
}
