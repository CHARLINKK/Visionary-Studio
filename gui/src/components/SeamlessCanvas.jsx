import React from 'react';
import { Stage } from 'react-konva';
import { useCanvasLayers } from '../hooks/useCanvasLayers';
import {
  CanvasBackgroundLayer,
  CanvasGuidesLayer,
  CanvasBubblesLayer,
  CanvasDrawingLayer,
  CanvasContextMenu,
} from './canvas';

/**
 * Componente principal do Canvas Konva do editor contínuo.
 * Responsável por renderizar a área vetorial interativa através de camadas especializadas.
 * Canvas limpo e desobstruído (Padrão Ouro: sem ilhas flutuantes sobre o mangá).
 */
const SeamlessCanvas = React.memo(function SeamlessCanvas() {
  const {
    containerRef,
    stageWrapperStyle,
    stageProps,
    backgroundProps,
    guidesProps,
    bubblesProps,
    drawingProps,
    contextMenuProps,
  } = useCanvasLayers();

  const stageRef = React.useRef(null);

  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      window.__VISIONARY_KONVA_STAGE__ = stageRef.current;
      window.__VISIONARY_ACTIVE_BOXES__ = bubblesProps?.boxes || [];
      window.__VISIONARY_SELECT_BUBBLE__ = bubblesProps?.actions?.select || null;
    }
    return () => {
      if (typeof window !== 'undefined' && window.__VISIONARY_KONVA_STAGE__ === stageRef.current) {
        window.__VISIONARY_KONVA_STAGE__ = null;
        window.__VISIONARY_SELECT_BUBBLE__ = null;
      }
    };
  }, [bubblesProps?.boxes, bubblesProps?.actions]);

  return (
    <div className="canvas-container" ref={containerRef}>
      <div 
        className="canvas-stage-wrapper"
        style={stageWrapperStyle}
      >
        <Stage ref={stageRef} {...stageProps}>
          <CanvasBackgroundLayer {...backgroundProps} />
          <CanvasGuidesLayer {...guidesProps} />
          <CanvasBubblesLayer {...bubblesProps} />
          <CanvasDrawingLayer {...drawingProps} />
        </Stage>
        {contextMenuProps?.isOpen && (
          <CanvasContextMenu {...contextMenuProps} />
        )}
      </div>
    </div>
  );
});

SeamlessCanvas.displayName = 'SeamlessCanvas';

export default SeamlessCanvas;
