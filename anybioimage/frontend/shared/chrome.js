// anybioimage/frontend/shared/chrome.js
//
// Shared UI chrome: builds the toolbar, layers panel, dimension controls,
// and status bar around a viewport slot. The caller is responsible for
// mounting the actual rendering surface (Canvas2D canvas, or a Viv React
// root) into the returned `viewportEl`.
//
// This module only writes to traitlets that exist on BioImageViewer. It does
// not read or depend on any backend-specific globals. The visual styling
// comes from the `_css` traitlet on BioImageViewer (shared by all backends).

const ICONS = {
  pan: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"/><path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/></svg>',
  select: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 3 7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/><path d="m13 13 6 6"/></svg>',
  reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>',
  eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
  eyeOff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>',
  layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
};

/**
 * Build the shared chrome. Returns an object with:
 *   - viewportEl: the div where the caller mounts its rendering surface
 *   - dispose: tears down event listeners + observers
 *
 * Options:
 *   - includeAnnotationTools (default false): show rect/polygon/point buttons.
 *     The Viv backend does not yet support these, so it leaves them off.
 *   - onReset (optional callback): invoked when the reset-view button is clicked.
 */
export function buildChrome({ model, el }, { onReset, onAutoContrast } = {}) {
  const container = document.createElement('div');
  container.className = 'bioimage-viewer';
  container.tabIndex = 0;
  el.appendChild(container);

  // --- Toolbar ---
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';

  const toolGroup = document.createElement('div');
  toolGroup.className = 'tool-group';

  function createToolBtn(icon, mode, title) {
    const btn = document.createElement('button');
    btn.className = 'tool-btn' + (model.get('tool_mode') === mode ? ' active' : '');
    btn.innerHTML = icon;
    btn.title = title;
    btn.dataset.mode = mode;
    btn.addEventListener('click', () => {
      model.set('tool_mode', mode);
      model.save_changes();
    });
    return btn;
  }

  const panBtn = createToolBtn(ICONS.pan, 'pan', 'Pan (P)');
  const selectBtn = createToolBtn(ICONS.select, 'select', 'Select (V)');
  toolGroup.appendChild(panBtn);
  toolGroup.appendChild(selectBtn);

  const sep1 = document.createElement('div');
  sep1.className = 'toolbar-separator';

  const actionGroup = document.createElement('div');
  actionGroup.className = 'tool-group';

  const resetBtn = document.createElement('button');
  resetBtn.className = 'tool-btn';
  resetBtn.innerHTML = ICONS.reset;
  resetBtn.title = 'Reset View';
  resetBtn.addEventListener('click', () => { if (onReset) onReset(); });
  actionGroup.appendChild(resetBtn);

  const sep2 = document.createElement('div');
  sep2.className = 'toolbar-separator';

  // --- Layers button + panel ---
  const layersGroup = document.createElement('div');
  layersGroup.className = 'layers-group';

  const layersBtn = document.createElement('button');
  layersBtn.className = 'layers-btn';
  layersBtn.innerHTML = ICONS.layers + '<span>Layers</span>';

  const layersPanel = document.createElement('div');
  layersPanel.className = 'layers-panel';

  let panelOpen = false;
  layersBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    panelOpen = !panelOpen;
    if (panelOpen) rebuildLayersPanel();
    layersPanel.classList.toggle('open', panelOpen);
    layersBtn.classList.toggle('active', panelOpen);
  });
  // Click-outside closes the panel. We check both the button group and the
  // panel itself since they now live in different subtrees (panel is a sidebar
  // of .content-area, button is in the .toolbar).
  const outsideClickHandler = (e) => {
    if (!panelOpen) return;
    if (layersGroup.contains(e.target)) return;
    if (layersPanel.contains(e.target)) return;
    panelOpen = false;
    layersPanel.classList.remove('open');
    layersBtn.classList.remove('active');
  };
  document.addEventListener('click', outsideClickHandler);

  function rebuildLayersPanel() {
    layersPanel.innerHTML = '';

    // Image visibility toggle
    const imageItem = document.createElement('div');
    imageItem.className = 'layer-item';
    const imageToggle = document.createElement('button');
    const imageVisible = model.get('image_visible') !== false;
    imageToggle.className = 'layer-toggle' + (imageVisible ? ' visible' : '');
    imageToggle.innerHTML = imageVisible ? ICONS.eye : ICONS.eyeOff;
    imageToggle.addEventListener('click', () => {
      const next = !(model.get('image_visible') !== false);
      model.set('image_visible', next);
      model.save_changes();
      imageToggle.classList.toggle('visible', next);
      imageToggle.innerHTML = next ? ICONS.eye : ICONS.eyeOff;
    });
    const imageLabel = document.createElement('span');
    imageLabel.textContent = 'Image';
    imageItem.appendChild(imageToggle);
    imageItem.appendChild(imageLabel);
    layersPanel.appendChild(imageItem);

    // Channel rows
    const channelSettings = model.get('_channel_settings') || [];
    channelSettings.forEach((ch, idx) => {
      const chRow = document.createElement('div');
      chRow.className = 'layer-item channel-layer-item';

      const chToggle = document.createElement('button');
      const visible = ch.visible !== false;
      chToggle.className = 'layer-toggle' + (visible ? ' visible' : '');
      chToggle.innerHTML = visible ? ICONS.eye : ICONS.eyeOff;
      chToggle.addEventListener('click', () => {
        const settings = [...model.get('_channel_settings')];
        const newVisible = !settings[idx].visible;
        settings[idx] = { ...settings[idx], visible: newVisible };
        model.set('_channel_settings', settings);
        model.save_changes();
      });

      const colorDot = document.createElement('span');
      colorDot.className = 'channel-dot';
      colorDot.style.backgroundColor = ch.color || '#ffffff';

      const chName = document.createElement('span');
      chName.className = 'channel-name';
      chName.textContent = ch.name || `Ch ${idx}`;

      const colorPicker = document.createElement('input');
      colorPicker.type = 'color';
      colorPicker.value = ch.color || '#ffffff';
      colorPicker.className = 'color-swatch';
      colorPicker.addEventListener('click', (e) => e.stopPropagation());
      colorPicker.addEventListener('input', () => {
        const settings = [...model.get('_channel_settings')];
        settings[idx] = { ...settings[idx], color: colorPicker.value };
        model.set('_channel_settings', settings);
        model.save_changes();
        colorDot.style.backgroundColor = colorPicker.value;
      });

      const autoBtn = document.createElement('button');
      autoBtn.className = 'auto-contrast-btn';
      autoBtn.textContent = 'Auto';
      autoBtn.title = 'Auto-contrast (5e-4/1−5e-4 percentile)';
      autoBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!onAutoContrast) return;
        autoBtn.textContent = '...';
        autoBtn.disabled = true;
        try {
          const result = await onAutoContrast(idx);
          if (result && Array.isArray(result) && result.length === 2) {
            const [lo, hi] = result;
            const settings = [...model.get('_channel_settings')];
            settings[idx] = { ...settings[idx], min: Math.max(0, Math.min(1, lo)), max: Math.max(0, Math.min(1, hi)) };
            model.set('_channel_settings', settings);
            model.save_changes();
            if (panelOpen) rebuildLayersPanel();
          }
        } finally {
          autoBtn.textContent = 'Auto';
          autoBtn.disabled = false;
        }
      });

      chRow.appendChild(chToggle);
      chRow.appendChild(colorDot);
      chRow.appendChild(chName);
      chRow.appendChild(autoBtn);
      chRow.appendChild(colorPicker);
      layersPanel.appendChild(chRow);

      // Min/Max sliders
      function createContrastRow(label, prop, initial) {
        const row = document.createElement('div');
        row.className = 'layer-item sub-item channel-contrast-row';
        const lbl = document.createElement('span');
        lbl.className = 'slider-label';
        lbl.textContent = label;
        const slider = document.createElement('input');
        slider.type = 'range';
        slider.min = '0';
        slider.max = '100';
        slider.value = String(Math.round(initial * 100));
        slider.className = 'adjustment-slider';
        const valEl = document.createElement('span');
        valEl.className = 'slider-value';
        valEl.textContent = Math.round(initial * 100) + '%';
        row.appendChild(lbl);
        row.appendChild(slider);
        row.appendChild(valEl);
        return { row, slider, valEl };
      }
      const minRow = createContrastRow('Min', 'min', ch.min ?? 0);
      const maxRow = createContrastRow('Max', 'max', ch.max ?? 1);
      layersPanel.appendChild(minRow.row);
      layersPanel.appendChild(maxRow.row);

      minRow.slider.addEventListener('input', () => {
        let v = parseInt(minRow.slider.value);
        const mv = parseInt(maxRow.slider.value);
        if (v >= mv) { v = mv - 1; minRow.slider.value = String(v); }
        const settings = [...model.get('_channel_settings')];
        settings[idx] = { ...settings[idx], min: v / 100 };
        model.set('_channel_settings', settings);
        model.save_changes();
        minRow.valEl.textContent = v + '%';
      });
      maxRow.slider.addEventListener('input', () => {
        let v = parseInt(maxRow.slider.value);
        const mv = parseInt(minRow.slider.value);
        if (v <= mv) { v = mv + 1; maxRow.slider.value = String(v); }
        const settings = [...model.get('_channel_settings')];
        settings[idx] = { ...settings[idx], max: v / 100 };
        model.set('_channel_settings', settings);
        model.save_changes();
        maxRow.valEl.textContent = v + '%';
      });
    });
  }

  // Only the button lives in the toolbar. The panel is a sidebar in .content-area.
  layersGroup.appendChild(layersBtn);

  toolbar.appendChild(toolGroup);
  toolbar.appendChild(sep1);
  toolbar.appendChild(actionGroup);
  toolbar.appendChild(sep2);
  toolbar.appendChild(layersGroup);

  container.appendChild(toolbar);

  // --- Dimension controls (T/Z sliders, scene/plate selectors) ---
  const dimControls = document.createElement('div');
  dimControls.className = 'dimension-controls';

  let playInterval = null;
  const playSpeed = 200;

  function createDimSlider(label, currentKey, maxVal, showPlayBtn = false) {
    const wrapper = document.createElement('div');
    wrapper.className = 'dim-slider-wrapper';

    const labelEl = document.createElement('span');
    labelEl.className = 'dim-label';
    labelEl.textContent = label;

    let playBtn = null;
    if (showPlayBtn && maxVal > 1) {
      playBtn = document.createElement('button');
      playBtn.className = 'play-btn';
      playBtn.innerHTML = '▶';
      playBtn.title = 'Play/Pause';
      playBtn.addEventListener('click', () => {
        if (playInterval) {
          clearInterval(playInterval);
          playInterval = null;
          playBtn.innerHTML = '▶';
        } else {
          playBtn.innerHTML = '⏸';
          playInterval = setInterval(() => {
            const next = ((model.get(currentKey) ?? 0) + 1) % maxVal;
            model.set(currentKey, next);
            model.save_changes();
          }, playSpeed);
        }
      });
    }

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = '0';
    slider.max = String(maxVal - 1);
    slider.value = String(model.get(currentKey) ?? 0);
    slider.className = 'dim-slider';

    const valueEl = document.createElement('span');
    valueEl.className = 'dim-value';
    valueEl.textContent = `${model.get(currentKey) ?? 0}/${maxVal}`;

    slider.addEventListener('input', () => {
      const v = parseInt(slider.value);
      valueEl.textContent = `${v}/${maxVal}`;
      model.set(currentKey, v);
      model.save_changes();
    });

    model.on(`change:${currentKey}`, () => {
      slider.value = String(model.get(currentKey));
      valueEl.textContent = `${model.get(currentKey)}/${maxVal}`;
    });

    wrapper.appendChild(labelEl);
    if (playBtn) wrapper.appendChild(playBtn);
    wrapper.appendChild(slider);
    wrapper.appendChild(valueEl);
    return wrapper;
  }

  function createSelector(label, listKey, currentKey) {
    const wrapper = document.createElement('div');
    wrapper.className = 'scene-selector-wrapper';
    const labelEl = document.createElement('span');
    labelEl.className = 'dim-label';
    labelEl.textContent = label;
    const select = document.createElement('select');
    select.className = 'scene-select';
    const items = model.get(listKey) || [];
    items.forEach((item) => {
      const opt = document.createElement('option');
      opt.value = item;
      opt.textContent = item;
      if (item === model.get(currentKey)) opt.selected = true;
      select.appendChild(opt);
    });
    select.addEventListener('change', () => {
      model.set(currentKey, select.value);
      model.save_changes();
    });
    wrapper.appendChild(labelEl);
    wrapper.appendChild(select);
    return wrapper;
  }

  function rebuildDimControls() {
    dimControls.innerHTML = '';
    const dimT = model.get('dim_t') || 1;
    const dimZ = model.get('dim_z') || 1;
    const scenes = model.get('scenes') || [];
    const plateWells = model.get('plate_wells') || [];
    const plateFovs = model.get('plate_fovs') || [];

    const hasMultiDim =
      dimT > 1 || dimZ > 1 || scenes.length > 1 || plateWells.length > 0;
    dimControls.style.display = hasMultiDim ? 'flex' : 'none';

    if (plateWells.length > 0) dimControls.appendChild(createSelector('Well', 'plate_wells', 'current_well'));
    if (plateFovs.length > 0) dimControls.appendChild(createSelector('FOV', 'plate_fovs', 'current_fov'));
    if (scenes.length > 1) dimControls.appendChild(createSelector('Scene', 'scenes', 'current_scene'));
    if (dimT > 1) dimControls.appendChild(createDimSlider('T', 'current_t', dimT, true));
    if (dimZ > 1) dimControls.appendChild(createDimSlider('Z', 'current_z', dimZ));
  }

  rebuildDimControls();

  ['dim_t', 'dim_z', 'scenes', 'plate_wells', 'plate_fovs'].forEach((k) => {
    model.on(`change:${k}`, rebuildDimControls);
  });
  // _channel_settings can change rapidly during slider drag. We rebuild the
  // layers panel on open rather than subscribing to every change — otherwise
  // mid-drag rebuilds steal focus from the slider and cause jitter.

  container.appendChild(dimControls);

  // --- Content area: viewport + layers sidebar ---
  const contentArea = document.createElement('div');
  contentArea.className = 'content-area';

  const viewportEl = document.createElement('div');
  viewportEl.className = 'viewport-slot';
  viewportEl.style.cssText = 'position:relative;flex:1;min-height:500px;background:#000';

  contentArea.appendChild(viewportEl);
  contentArea.appendChild(layersPanel);
  container.appendChild(contentArea);

  // --- Status bar ---
  const statusBar = document.createElement('div');
  statusBar.className = 'status-bar';
  const dimStatus = document.createElement('span');
  dimStatus.className = 'status-item dim-status';
  function updateDimStatus() {
    const t = model.get('current_t') ?? 0;
    const z = model.get('current_z') ?? 0;
    const dt = model.get('dim_t') ?? 1;
    const dz = model.get('dim_z') ?? 1;
    const parts = [];
    if (dt > 1) parts.push(`T ${t + 1}/${dt}`);
    if (dz > 1) parts.push(`Z ${z + 1}/${dz}`);
    dimStatus.textContent = parts.join(' · ');
  }
  updateDimStatus();
  ['current_t', 'current_z', 'dim_t', 'dim_z'].forEach((k) =>
    model.on(`change:${k}`, updateDimStatus),
  );
  statusBar.appendChild(dimStatus);
  container.appendChild(statusBar);

  return {
    viewportEl,
    dispose: () => {
      if (playInterval) clearInterval(playInterval);
      document.removeEventListener('click', outsideClickHandler);
    },
  };
}
