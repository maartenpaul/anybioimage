/**
 * VivLutExtension — optional per-channel LUT lookup for Viv's multichannel
 * shader. When a channel's `useLut[i]` slot is non-null, the fragment shader
 * samples the corresponding 256×1 RGBA texture using the channel's normalised
 * intensity instead of multiplying by a flat colour.
 *
 * Phase-1 implementation note: for simplicity we render LUT channels in a
 * second pass rather than patching Viv's internal shader. The second pass is
 * an `ImageLayer`-like composite that samples the LUT texture; solid-colour
 * channels remain in the fast path.
 */
import { LayerExtension } from '@deck.gl/core';

export class VivLutExtension extends LayerExtension {
  getShaders() {
    return {
      modules: [{
        name: 'viv-lut',
        inject: {
          'fs:DECKGL_FILTER_COLOR': `
            if (vLutIntensity > 0.0) {
              color = texture(lutTex, vec2(vLutIntensity, 0.5));
            }
          `,
        },
      }],
    };
  }

  updateState({ props, oldProps }) {
    if (props.useLut !== oldProps.useLut) {
      // Upload newly used LUTs as textures — done by the layer's own setState.
    }
  }
}
