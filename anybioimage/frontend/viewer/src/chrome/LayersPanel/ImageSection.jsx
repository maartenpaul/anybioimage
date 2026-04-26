// anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx
//
// Per-channel rows: visibility toggle, color/LUT picker, auto-contrast,
// and Min/Max/Gamma sliders. Each slider is paired with a NumericInput.
// Min/Max display data values (dtype-aware formatter); the stored traits
// are normalized [0, 1] using ch.data_min / ch.data_max.
import React from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';
import { listLuts } from '../../render/luts/index.js';
import { NumericInput } from '../NumericInput.jsx';

// Dtype-aware data-value formatter. Accepts both "uint16" and "Uint16".
function pickFormatter(dtype) {
  switch ((dtype || '').toLowerCase()) {
    case 'uint8':
    case 'uint16':
      return (n) => Math.round(n).toString();
    case 'uint32':
      return (n) => {
        const abs = Math.abs(n);
        if (n === 0) return '0';
        if (abs >= 1e6 || abs < 1) return n.toExponential(2);
        return Math.round(n).toString();
      };
    default:
      // float32 / float64 / unknown — 4 sig figs
      return (n) => (n === 0 ? '0' : Number(n).toPrecision(4));
  }
}

function normalizedToData(norm, ch) {
  const lo = ch.data_min ?? 0;
  const hi = ch.data_max ?? 65535;
  return lo + norm * (hi - lo);
}

function dataToNormalized(data, ch) {
  const lo = ch.data_min ?? 0;
  const hi = ch.data_max ?? 65535;
  const span = Math.max(hi - lo, 1);
  return (data - lo) / span;
}

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
        aria-label={visible ? 'Hide image' : 'Show image'}
        style={{ background: 'none', border: 'none', cursor: 'pointer' }}
        title={visible ? 'Hide image' : 'Show image'}>
        {visible ? '👁' : '⊘'}
      </button>
      <span style={{ flex: 1 }}>Image</span>
      <select value={displayMode}
        aria-label="Display mode"
        onChange={(e) => { model.set('_display_mode', e.target.value); model.save_changes(); }}>
        <option value="composite">Composite</option>
        <option value="single">Single</option>
      </select>
    </div>
  );
}

function ChannelRow({ model, ch, idx, active, onActivate, formatter }) {
  const luts = listLuts();
  const dataMin = ch.data_min ?? 0;
  const dataMax = ch.data_max ?? 65535;
  const minDisplayed = normalizedToData(ch.min ?? 0, ch);
  const maxDisplayed = normalizedToData(ch.max ?? 1, ch);

  const commitMin = (data) => setChannel(model, idx, {
    min: Math.max(0, Math.min(1, dataToNormalized(data, ch))),
  });
  const commitMax = (data) => setChannel(model, idx, {
    max: Math.max(0, Math.min(1, dataToNormalized(data, ch))),
  });

  return (
    <>
      <div className={'layer-item channel-layer-item' + (active ? ' active-channel' : '')}
           onClick={onActivate}
           style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0',
                    background: active ? '#eef5ff' : 'transparent', cursor: 'pointer' }}>
        <button className={'layer-toggle' + (ch.visible ? ' visible' : '')}
          onClick={(e) => { e.stopPropagation(); setChannel(model, idx, { visible: !ch.visible }); }}
          aria-label={ch.visible ? 'Hide channel' : 'Show channel'}
          title={ch.visible ? 'Hide channel' : 'Show channel'}
          style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
          {ch.visible ? '👁' : '⊘'}
        </button>
        <span className="channel-name" style={{ flex: 1, fontSize: 12 }}>{ch.name || `Ch ${idx}`}</span>

        <select value={ch.color_kind || 'solid'}
          aria-label="Color mode"
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setChannel(model, idx, { color_kind: e.target.value })}
          style={{ fontSize: 11 }}>
          <option value="solid">Solid</option>
          <option value="lut">LUT</option>
        </select>

        {ch.color_kind === 'lut' ? (
          <select value={ch.lut || 'viridis'}
            aria-label="LUT"
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { lut: e.target.value })}
            style={{ fontSize: 11 }}>
            {luts.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        ) : (
          <input type="color" value={ch.color || '#ffffff'}
            aria-label="Channel color"
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { color: e.target.value })}
            style={{ width: 24, height: 20, border: 'none', padding: 0 }} />
        )}

        <button className="auto-contrast-btn"
          aria-label="Auto contrast"
          title="Auto contrast"
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
          aria-label="Channel min"
          onChange={(e) => setChannel(model, idx, { min: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <NumericInput
          value={minDisplayed}
          min={dataMin} max={dataMax}
          format={formatter}
          onCommit={commitMin}
          aria-label="Channel min value"
          style={{ width: 72, fontSize: 11, padding: '1px 4px' }} />
      </div>

      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Max</span>
        <input type="range" min="0" max="100" value={Math.round((ch.max ?? 1) * 100)}
          aria-label="Channel max"
          onChange={(e) => setChannel(model, idx, { max: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <NumericInput
          value={maxDisplayed}
          min={dataMin} max={dataMax}
          format={formatter}
          onCommit={commitMax}
          aria-label="Channel max value"
          style={{ width: 72, fontSize: 11, padding: '1px 4px' }} />
      </div>

      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Gamma</span>
        <input type="range" min="10" max="500" value={Math.round((ch.gamma ?? 1) * 100)}
          aria-label="Channel gamma"
          onChange={(e) => setChannel(model, idx, { gamma: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <NumericInput
          value={ch.gamma ?? 1}
          min={0.1} max={5}
          format={(n) => n.toFixed(2)}
          onCommit={(n) => setChannel(model, idx, { gamma: n })}
          aria-label="Channel gamma value"
          style={{ width: 56, fontSize: 11, padding: '1px 4px' }} />
        <button className="reset-gamma-btn"
          aria-label="Reset gamma to 1"
          title="Reset gamma to 1"
          onClick={(e) => { e.stopPropagation(); setChannel(model, idx, { gamma: 1.0 }); }}
          style={{ fontSize: 11, padding: '2px 6px' }}>1</button>
      </div>
    </>
  );
}

export function ImageSection({ model }) {
  const channels = useModelTrait(model, '_channel_settings') || [];
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  const dtype = useModelTrait(model, '_image_dtype') || 'uint16';
  const formatter = pickFormatter(dtype);
  return (
    <>
      <ImageRow model={model} />
      {channels.map((ch, idx) => (
        <ChannelRow key={idx} model={model} ch={ch} idx={idx}
          active={idx === activeChannel}
          formatter={formatter}
          onActivate={() => { model.set('current_c', idx); model.save_changes(); }} />
      ))}
    </>
  );
}
