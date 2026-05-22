// anybioimage/frontend/viewer/src/interaction/tools/select.js
/** Select tool — click-to-select an annotation. Drag / vertex edit are Phase 3.
 *
 *  The `ctx.pickObject(event)` callback is supplied by DeckCanvas; it wraps
 *  the deck.gl picking API and returns either null or `{layer, object,
 *  sourceAnnotation}` — where `sourceAnnotation` is the full `_annotations`
 *  entry if the layer composer attached it.
 */
function kindFromLayerId(id) {
  if (id === 'annotations-points') return 'point';
  if (id === 'annotations-polygons') return 'rect';   // rect and polygon share the layer
  return '';
}

export const selectTool = {
  id: 'select',
  cursor: 'default',
  onPointerDown() {},
  onPointerMove() {},
  onPointerUp(event, ctx) {
    const picked = typeof ctx.pickObject === 'function' ? ctx.pickObject(event) : null;
    if (!picked) {
      ctx.model.set('selected_annotation_id', '');
      ctx.model.set('selected_annotation_type', '');
      ctx.model.save_changes();
      return;
    }
    const id = picked.sourceAnnotation?.id ?? picked.object?.id ?? '';
    const kind = picked.sourceAnnotation?.kind
              || kindFromLayerId(picked.layer?.id)
              || '';
    ctx.model.set('selected_annotation_id', id);
    ctx.model.set('selected_annotation_type', kind);
    ctx.model.save_changes();
  },
  onKeyDown() {},
  getPreviewLayer() { return null; },
};
