import gray from './lut-textures/gray.png';
import viridis from './lut-textures/viridis.png';
import plasma from './lut-textures/plasma.png';
import magma from './lut-textures/magma.png';
import inferno from './lut-textures/inferno.png';
import cividis from './lut-textures/cividis.png';
import turbo from './lut-textures/turbo.png';
import hot from './lut-textures/hot.png';
import cool from './lut-textures/cool.png';
import red from './lut-textures/red.png';
import green from './lut-textures/green.png';
import blue from './lut-textures/blue.png';
import cyan from './lut-textures/cyan.png';
import magenta from './lut-textures/magenta.png';
import yellow from './lut-textures/yellow.png';

const SOURCES = {
  gray, viridis, plasma, magma, inferno, cividis, turbo, hot, cool,
  red, green, blue, cyan, magenta, yellow,
};

const _cache = new Map();

export function listLuts() {
  return Object.keys(SOURCES);
}

export async function getLutTexture(name) {
  if (_cache.has(name)) return _cache.get(name);
  const src = SOURCES[name];
  if (!src) throw new Error(`unknown LUT: ${name}`);
  const img = new Image();
  img.src = src;
  await (img.decode ? img.decode() : new Promise((res) => { img.onload = res; }));
  const canvas = document.createElement('canvas');
  canvas.width = 256; canvas.height = 1;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const pixels = ctx.getImageData(0, 0, 256, 1).data;
  const out = new Uint8Array(256 * 4);
  out.set(pixels);
  _cache.set(name, out);
  return out;
}
