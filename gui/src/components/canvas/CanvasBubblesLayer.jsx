import React from 'react';
import { Layer } from 'react-konva';
import { BubbleShape } from '../BubbleShape';

/**
 * @typedef {import('../../types/bubble').Bubble} Bubble
 *
 * @typedef {Object} CanvasBubblesLayerProps
 * @property {Array<Bubble>} [boxes] Lista ordenada de caixas/balões
 * @property {number} scale Escala de visualização do canvas
 * @property {{ width: number, height: number }} bgSize Dimensões originais da página
 * @property {string} viewMode Modo de visualização ativo
 * @property {string} activeTool Ferramenta ativa selecionada
 * @property {string|number|null} [activeBubbleId] ID do balão atualmente em foco
 * @property {string|number|null} [dragStartPos] ID do balão em reordenação
 * @property {string|number|null} [rectStartPos] ID do balão de origem em ligação
 * @property {Array<string|number>} [bubbles] Fila de balões na ferramenta de sequência
 * @property {Object} [actions] Objeto controlador com ações de balão (useBubbleActions)
 * @property {Function} [setOcrData] Setter de estado das caixas OCR (legado)
 * @property {Function} [setActiveBubbleId] Função para selecionar balão ativo (legado)
 * @property {Function} [setDragStartPos] Setter de coordenadas de arraste (legado)
 * @property {Function} [pushHistory] Função para gravar estado na pilha de desfazer (legado)
 * @property {Function} [startHistoryTransaction] Inicia transação de histórico (legado)
 * @property {Function} [commitHistoryTransaction] Confirma transação de histórico (legado)
 * @property {Function} [debouncedHistoryUpdate] Atualização debounced de histórico (legado)
 * @property {Function} [setBubbles] Setter da lista de balões (legado)
 * @property {Function} [setRectStartPos] Setter do ponto inicial do retângulo (legado)
 * @property {Function} [updateBubbleProperties] Atualizador atômico de propriedades de balão (legado)
 */

/**
 * Camada Konva responsável pela renderização interativa dos balões da página.
 * Otimizada para computar flags atômicas e isolar re-renderizações via React.memo.
 * @type {React.FC<CanvasBubblesLayerProps>}
 */
export const CanvasBubblesLayer = React.memo(function CanvasBubblesLayer({
  boxes = [],
  scale,
  bgSize,
  viewMode = 'layout',
  activeTool = 'select',
  activeBubbleId = null,
  dragStartPos = null,
  rectStartPos = null,
  bubbles = [],
  actions = null,
  bubbleContourMode = 'polygon',
  bubbleEditMode = 'box',
  setBubbleEditMode,
  // Props legadas
  setOcrData,
  setActiveBubbleId,
  setDragStartPos,
  pushHistory,
  startHistoryTransaction,
  commitHistoryTransaction,
  debouncedHistoryUpdate,
  setBubbles,
  setRectStartPos,
  updateBubbleProperties,
}) {
  const isSequence = activeTool === 'sequence';
  const isReorder = activeTool === 'reorder';
  const isLink = activeTool === 'link';

  return (
    <Layer id="interactive-layer">
      {boxes.map((b, i) => (
        <BubbleShape
          key={b.id}
          b={b}
          i={i}
          scale={scale}
          bgSize={bgSize}
          totalBubbles={boxes.length}
          viewMode={viewMode}
          activeTool={activeTool}
          // Props derivadas atômicas para React.memo de alta performance
          isSelected={activeBubbleId === b.id}
          isReorderSource={isReorder && dragStartPos === b.id}
          isLinkSource={isLink && rectStartPos === b.id}
          sequenceIndex={isSequence && Array.isArray(bubbles) ? bubbles.indexOf(b.id) : -1}
          actions={actions}
          bubbleContourMode={bubbleContourMode}
          bubbleEditMode={bubbleEditMode}
          setBubbleEditMode={setBubbleEditMode}
          // Props legadas para compatibilidade regressiva
          activeBubbleId={activeBubbleId}
          setActiveBubbleId={setActiveBubbleId}
          dragStartPos={dragStartPos}
          setDragStartPos={setDragStartPos}
          pushHistory={pushHistory}
          startHistoryTransaction={startHistoryTransaction}
          commitHistoryTransaction={commitHistoryTransaction}
          debouncedHistoryUpdate={debouncedHistoryUpdate}
          bubbles={bubbles}
          setBubbles={setBubbles}
          rectStartPos={rectStartPos}
          setRectStartPos={setRectStartPos}
          updateBubbleProperties={updateBubbleProperties}
          setOcrData={setOcrData}
        />
      ))}
    </Layer>
  );
});
