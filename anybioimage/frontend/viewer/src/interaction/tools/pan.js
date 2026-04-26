// anybioimage/frontend/viewer/src/interaction/tools/pan.js
/** Pan tool — all pointer handling is delegated to deck.gl's view controller.
 *  This module exists so that every tool follows the same registry shape. */
export const panTool = {
  id: 'pan',
  cursor: 'grab',
  onPointerDown() {},
  onPointerMove() {},
  onPointerUp() {},
  onKeyDown() {},
  getPreviewLayer() { return null; },
};
