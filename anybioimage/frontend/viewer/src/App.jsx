// anybioimage/frontend/viewer/src/App.jsx
import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Toolbar } from './chrome/Toolbar.jsx';
import { DimControls } from './chrome/DimControls.jsx';
import { StatusBar } from './chrome/StatusBar.jsx';
import { LayersPanel } from './chrome/LayersPanel/LayersPanel.jsx';
import { DeckCanvas } from './render/DeckCanvas.jsx';
import { installKeyboard } from './interaction/keyboard.js';
import { makeHoverHandler } from './render/onHoverPixelInfo.js';
import { InteractionController } from './interaction/InteractionController.js';
import { panTool } from './interaction/tools/pan.js';
import { selectTool } from './interaction/tools/select.js';
import { rectTool } from './interaction/tools/rect.js';
import { polygonTool } from './interaction/tools/polygon.js';
import { pointTool } from './interaction/tools/point.js';
import { MaskSourceBridge } from './render/pixel-sources/MaskSourceBridge.js';

export function App({ model }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const sourcesRef = useRef(null);
  const selectionsRef = useRef(null);
  const deckRef = useRef(null);

  const controller = useMemo(() => {
    const c = new InteractionController(model);
    c.register(panTool);
    c.register(selectTool);
    c.register(rectTool);
    c.register(polygonTool);
    c.register(pointTool);
    return c;
  }, [model]);

  const maskBridge = useMemo(() => new MaskSourceBridge(model), [model]);
  useEffect(() => () => maskBridge.destroy(), [maskBridge]);

  useEffect(() => {
    const handler = () => {
      rectTool.reset();
      polygonTool.reset();
    };
    model.on('change:tool_mode', handler);
    return () => model.off('change:tool_mode', handler);
  }, [model, controller]);

  const onHover = useMemo(
    () => makeHoverHandler({
      getSources: () => sourcesRef.current,
      getSelections: () => selectionsRef.current,
      setHover,
    }),
    []);

  useEffect(() => installKeyboard(model), [model]);

  return (
    <div className="bioimage-viewer" tabIndex={0}>
      <Toolbar model={model} onToggleLayers={() => setPanelOpen((v) => !v)} panelOpen={panelOpen} />
      <DimControls model={model} />
      <div className="content-area" style={{ display: 'flex', flex: 1, minHeight: 500 }}>
        <div className="viewport-slot" style={{ position: 'relative', flex: 1, minHeight: 500, background: '#000' }}>
          <DeckCanvas model={model} onHover={onHover}
                      controller={controller}
                      maskBridge={maskBridge}
                      deckRef={deckRef}
                      sourcesRef={sourcesRef}
                      selectionsRef={selectionsRef} />
        </div>
        {panelOpen && <LayersPanel model={model} />}
      </div>
      <StatusBar model={model} hover={hover} />
    </div>
  );
}
