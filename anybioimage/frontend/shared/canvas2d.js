// Canvas2D stub — replaced by Viv bundle in Task 18.
export default function render(el, model) {
  el.innerHTML = '<canvas class="viewer-canvas"></canvas>';
  const canvas = el.querySelector('canvas');
  if (canvas) { canvas.width = 800; canvas.height = 600; }
}
