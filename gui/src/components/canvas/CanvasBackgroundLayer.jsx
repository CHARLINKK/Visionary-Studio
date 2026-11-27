import React from 'react';
import { Layer, Image, Rect } from 'react-konva';

/**
 * @typedef {Object} CanvasBackgroundLayerProps
 * @property {HTMLImageElement|null} [bgImage] Imagem de fundo carregada
 * @property {{ width: number, height: number }} [bgSize] Dimensões originais da imagem
 */

/**
 * Camada pura de fundo do Konva Stage.
 * @type {React.FC<CanvasBackgroundLayerProps>}
 */
export const CanvasBackgroundLayer = React.memo(function CanvasBackgroundLayer({ bgImage, bgSize }) {
  return (
    <Layer id="bg-layer" listening={false}>
      {bgImage ? (
        <Image
          image={bgImage}
          name="bg-image"
          width={bgSize?.width || 800}
          height={bgSize?.height || 1200}
        />
      ) : (
        <Rect
          id="bg-layer-rect"
          width={800}
          height={1200}
          fill="#1e293b"
        />
      )}
    </Layer>
  );
});
