import { useCallback, useMemo } from 'react';
import {
  reindexBubbleOrders,
  getBubbleGroupId,
  stripBubbleGroupId,
  toggleBubbleSfxState,
} from '../utils/bubbleNormalizer';
import { inflatePolygon, computeBboxFromPolygon } from '../utils/polygonGeometry';

/**
 * @typedef {import('../types/bubble').Bubble} Bubble
 *
 * @typedef {Object} BubbleActionsHookParams
 * @property {Function} [setOcrData] Setter do estado OCR do SeamlessContext
 * @property {Function} [setActiveBubbleId] Setter para seleção de balão ativo
 * @property {Function} [pushHistory] Função para gravar snapshot na pilha de desfazer
 * @property {Function} [startHistoryTransaction] Inicia transação atômica de histórico
 * @property {Function} [commitHistoryTransaction] Confirma e encerra transação de histórico
 * @property {{ width: number, height: number }} [bgSize] Dimensões da página em pixels
 * @property {Object} [tools] Estado transitório das ferramentas do canvas
 * @property {string|number|null} [tools.dragStartPos] ID do balão de origem durante reordenação
 * @property {Function} [tools.setDragStartPos] Setter do balão de origem durante reordenação
 * @property {string|number|null} [tools.rectStartPos] ID do balão de origem durante linking
 * @property {Function} [tools.setRectStartPos] Setter do balão de origem durante linking
 * @property {Array<string|number>} [tools.bubbles] Fila de balões selecionados na ferramenta de sequência
 * @property {Function} [tools.setBubbles] Setter da fila de sequência
 */

/**
 * Hook central para orquestrar operações de mutação de balões (OCR) no canvas Konva,
 * isolando transações de histórico, manipulação de arrays e restrições espaciais.
 *
 * @param {BubbleActionsHookParams} params
 */
export function useBubbleActions({
  setOcrData,
  setActiveBubbleId,
  pushHistory,
  startHistoryTransaction,
  commitHistoryTransaction,
  bgSize = { width: 800, height: 1200 },
  tools = {},
  openContextMenu = null,
} = {}) {
  const {
    dragStartPos = null,
    setDragStartPos = () => {},
    rectStartPos = null,
    setRectStartPos = () => {},
    bubbles = [],
    setBubbles = () => {},
  } = tools;

  /**
   * Alterna a seleção de um balão ou desmarca se já selecionado.
   */
  const selectBubble = useCallback((bubbleId) => {
    if (setActiveBubbleId) {
      setActiveBubbleId((prev) => (prev === bubbleId ? null : bubbleId));
    }
  }, [setActiveBubbleId]);

  /**
   * Atualização atômica de propriedades parciais de um balão no OCR.
   */
  const updateBubble = useCallback((bubbleId, partialProps) => {
    if (!setOcrData) return;
    setOcrData((data) => {
      if (!data?.boxes) return data;
      return {
        ...data,
        boxes: data.boxes.map((x) =>
          x.id === bubbleId ? { ...x, ...partialProps } : x
        ),
      };
    });
  }, [setOcrData]);

  /**
   * Alterna a natureza do balão entre fala e efeito sonoro (SFX),
   * atualizando flags morfológicas e reindexando a ordem de leitura.
   */
  const toggleSfx = useCallback((bubbleId) => {
    if (!setOcrData) return;
    setOcrData((data) => {
      if (!data?.boxes) return data;
      if (pushHistory) pushHistory(data);
      const updatedBoxes = data.boxes.map((b) =>
        b.id !== bubbleId ? b : toggleBubbleSfxState(b)
      );
      return {
        ...data,
        boxes: reindexBubbleOrders(updatedBoxes),
      };
    });
  }, [setOcrData, pushHistory]);

  /**
   * Exclui um balão do OCR, limpa referências a grupos órfãos e reordena os índices.
   */
  const deleteBubble = useCallback((bubbleId, groupId = null) => {
    if (!setOcrData) return;
    setOcrData((data) => {
      if (!data?.boxes) return data;
      if (pushHistory) pushHistory(data);
      const targetBox = data.boxes.find((x) => x.id === bubbleId);
      const effectiveGroupId = groupId ?? getBubbleGroupId(targetBox);
      let filtered = data.boxes.filter((x) => x.id !== bubbleId);
      if (effectiveGroupId) {
        const remainingInGroup = filtered.filter(
          (x) => getBubbleGroupId(x) === effectiveGroupId
        );
        if (remainingInGroup.length <= 1) {
          filtered = filtered.map((x) =>
            getBubbleGroupId(x) === effectiveGroupId ? stripBubbleGroupId(x) : x
          );
        }
      }
      return {
        ...data,
        boxes: reindexBubbleOrders(filtered),
      };
    });
    if (setActiveBubbleId) {
      setActiveBubbleId((prev) => (prev === bubbleId ? null : prev));
    }
  }, [setOcrData, pushHistory, setActiveBubbleId]);

  /**
   * Reordena a posição de balões na lista (ordem de leitura).
   */
  const reorderBubble = useCallback((targetBubbleId) => {
    if (dragStartPos === null) {
      setDragStartPos(targetBubbleId);
      return;
    }
    if (dragStartPos !== targetBubbleId) {
      if (setOcrData) {
        setOcrData((data) => {
          if (!data?.boxes) return data;
          if (pushHistory) pushHistory(data);
          const arr = [...data.boxes];
          const i1 = arr.findIndex((x) => x.id === dragStartPos);
          const i2 = arr.findIndex((x) => x.id === targetBubbleId);
          if (i1 > -1 && i2 > -1) {
            const el = arr.splice(i1, 1)[0];
            arr.splice(i2, 0, el);
            return {
              ...data,
              boxes: reindexBubbleOrders(arr),
            };
          }
          return data;
        });
      }
      setDragStartPos(null);
    }
  }, [dragStartPos, setDragStartPos, setOcrData, pushHistory]);

  /**
   * Adiciona balões na fila sequencial e atualiza ordens quando todos forem marcados.
   */
  const sequenceBubble = useCallback((bubbleId, totalBubbles) => {
    if (!bubbles.includes(bubbleId)) {
      const nextB = [...bubbles, bubbleId];
      setBubbles(nextB);
      if (nextB.length === totalBubbles) {
        if (setOcrData) {
          setOcrData((data) => {
            if (!data?.boxes) return data;
            if (pushHistory) pushHistory(data);
            const sorted = nextB
              .map((id) => data.boxes.find((x) => x.id === id))
              .filter(Boolean);
            return {
              ...data,
              boxes: reindexBubbleOrders(sorted),
            };
          });
        }
        setBubbles([]);
      }
    }
  }, [bubbles, setBubbles, setOcrData, pushHistory]);

  /**
   * Conecta dois balões atribuindo um group_id em comum.
   * Se ambos já estiverem no mesmo grupo, desvincula o segundo balão (toggle de link).
   * Se clicar no mesmo balão duas vezes, desfaz a seleção inicial.
   */
  const linkBubble = useCallback((targetBubbleId) => {
    if (rectStartPos === null) {
      setRectStartPos(targetBubbleId);
      return;
    }
    if (rectStartPos === targetBubbleId) {
      setRectStartPos(null);
      return;
    }
    if (setOcrData) {
      setOcrData((data) => {
        if (!data?.boxes) return data;
        const arr = [...data.boxes];
        const i1 = arr.findIndex((x) => x.id === rectStartPos);
        const i2 = arr.findIndex((x) => x.id === targetBubbleId);
        if (i1 > -1 && i2 > -1) {
          const b1 = arr[i1];
          const b2 = arr[i2];
          const g1 = getBubbleGroupId(b1);
          const g2 = getBubbleGroupId(b2);

          // Se ambos já compartilham o mesmo grupo, toggle: desvincula o targetBubbleId
          if (g1 && g2 && g1 === g2) {
            if (pushHistory) pushHistory(data);
            let updated = arr.map((x) =>
              x.id === targetBubbleId ? stripBubbleGroupId(x) : x
            );
            const remaining = updated.filter((x) => getBubbleGroupId(x) === g1);
            if (remaining.length <= 1) {
              updated = updated.map((x) =>
                getBubbleGroupId(x) === g1 ? stripBubbleGroupId(x) : x
              );
            }
            return {
              ...data,
              boxes: updated,
            };
          }

          if (pushHistory) pushHistory(data);
          const gId = g1 || g2 || String(rectStartPos);
          arr[i1] = { ...arr[i1], group_id: gId };
          arr[i2] = { ...arr[i2], group_id: gId };
          return {
            ...data,
            boxes: arr,
          };
        }
        return data;
      });
    }
    setRectStartPos(null);
  }, [rectStartPos, setRectStartPos, setOcrData, pushHistory]);

  /**
   * Desvincula um balão do grupo e dissolve o grupo se sobrar apenas um integrante.
   */
  const unlinkBubble = useCallback((bubbleId, groupId = null) => {
    if (setOcrData) {
      setOcrData((data) => {
        if (!data?.boxes) return data;
        const targetBox = data.boxes.find((x) => x.id === bubbleId);
        const effectiveGroupId = groupId ?? getBubbleGroupId(targetBox);
        if (!effectiveGroupId) return data;

        if (pushHistory) pushHistory(data);
        let arr = data.boxes.map((x) =>
          x.id === bubbleId ? stripBubbleGroupId(x) : x
        );
        const remaining = arr.filter(
          (x) => getBubbleGroupId(x) === effectiveGroupId
        );
        if (remaining.length <= 1) {
          arr = arr.map((x) =>
            getBubbleGroupId(x) === effectiveGroupId ? stripBubbleGroupId(x) : x
          );
        }
        return {
          ...data,
          boxes: arr,
        };
      });
    }
    if (setRectStartPos) setRectStartPos(null);
  }, [setOcrData, pushHistory, setRectStartPos]);

  /**
   * Dispara abertura de transação atômica de histórico antes de arrasto ou redimensionamento.
   */
  const dragStart = useCallback(() => {
    if (startHistoryTransaction) {
      startHistoryTransaction();
    }
  }, [startHistoryTransaction]);

  /**
   * Conclui arrasto de balão restringindo às bordas da imagem e gravando transação.
   */
  const dragEnd = useCallback((bubble, dx, dy) => {
    if (Math.hypot(dx, dy) < 4) {
      if (commitHistoryTransaction) commitHistoryTransaction();
      return;
    }
    const cw = bgSize?.width || 800;
    const ch = bgSize?.height || 1200;
    const ox = Math.max(-bubble.x1, Math.min(cw - bubble.x2, dx));
    const oy = Math.max(-bubble.y1, Math.min(ch - bubble.y2, dy));

    if (bubble.polygon && bubble.polygon.length === 4 && bubble.label === 'text_tool') {
      const nextPoly = bubble.polygon.map((p) => [
        Math.max(0, Math.min(cw, p[0] + ox)),
        Math.max(0, Math.min(ch, p[1] + oy)),
      ]);
      updateBubble(bubble.id, {
        polygon: nextPoly,
        x1: Math.min(...nextPoly.map((p) => p[0])),
        y1: Math.min(...nextPoly.map((p) => p[1])),
        x2: Math.max(...nextPoly.map((p) => p[0])),
        y2: Math.max(...nextPoly.map((p) => p[1])),
        initial_box: bubble.initial_box || [bubble.x1, bubble.y1, bubble.x2, bubble.y2],
        initial_polygon: bubble.initial_polygon || bubble.polygon,
      });
    } else {
      const nextPoly =
        bubble.polygon && bubble.polygon.length > 0
          ? bubble.polygon.map((p) => [
              Math.max(0, Math.min(cw, p[0] + ox)),
              Math.max(0, Math.min(ch, p[1] + oy)),
            ])
          : bubble.polygon;
      updateBubble(bubble.id, {
        x1: Math.max(0, Math.min(cw, bubble.x1 + ox)),
        y1: Math.max(0, Math.min(ch, bubble.y1 + oy)),
        x2: Math.max(0, Math.min(cw, bubble.x2 + ox)),
        y2: Math.max(0, Math.min(ch, bubble.y2 + oy)),
        polygon: nextPoly,
        initial_box: bubble.initial_box || [bubble.x1, bubble.y1, bubble.x2, bubble.y2],
        initial_polygon: bubble.initial_polygon || bubble.polygon,
      });
    }
    if (commitHistoryTransaction) commitHistoryTransaction();
  }, [bgSize, updateBubble, commitHistoryTransaction]);

  /**
   * Restaura o balão para as coordenadas e contorno de detecção iniciais.
   */
  const resetBubblePosition = useCallback((bubbleId) => {
    if (!setOcrData) return;
    setOcrData((data) => {
      if (!data?.boxes) return data;
      const target = data.boxes.find((x) => x.id === bubbleId);
      if (!target) return data;

      const ibox = Array.isArray(target.initial_box) && target.initial_box.length === 4
        ? target.initial_box
        : [target.x1, target.y1, target.x2, target.y2];

      const ipoly = Array.isArray(target.initial_polygon) && target.initial_polygon.length > 0
        ? target.initial_polygon
        : target.polygon;

      if (pushHistory) pushHistory(data);

      return {
        ...data,
        boxes: data.boxes.map((b) => {
          if (b.id !== bubbleId) return b;
          return {
            ...b,
            x1: ibox[0],
            y1: ibox[1],
            x2: ibox[2],
            y2: ibox[3],
            polygon: ipoly ? JSON.parse(JSON.stringify(ipoly)) : b.polygon,
          };
        }),
      };
    });
  }, [setOcrData, pushHistory]);

  /**
   * Expande ou encolhe o balão (+/- deltaPx).
   */
  const inflateMargin = useCallback((bubbleId, deltaPx) => {
    if (!setOcrData) return;
    setOcrData((data) => {
      if (!data?.boxes) return data;
      const target = data.boxes.find((x) => x.id === bubbleId);
      if (!target) return data;

      if (pushHistory) pushHistory(data);

      return {
        ...data,
        boxes: data.boxes.map((b) => {
          if (b.id !== bubbleId) return b;
          if (b.polygon && Array.isArray(b.polygon) && b.polygon.length >= 3) {
            const nextPoly = inflatePolygon(b.polygon, deltaPx);
            const nextBbox = computeBboxFromPolygon(nextPoly);
            return {
              ...b,
              polygon: nextPoly,
              ...nextBbox,
              user_edited: true,
            };
          }
          return {
            ...b,
            x1: Math.max(0, b.x1 - deltaPx),
            y1: Math.max(0, b.y1 - deltaPx),
            x2: Math.max(b.x1 + 10, b.x2 + deltaPx),
            y2: Math.max(b.y1 + 10, b.y2 + deltaPx),
            user_edited: true,
          };
        }),
      };
    });
  }, [setOcrData, pushHistory]);

  return useMemo(() => ({
    select: selectBubble,
    update: updateBubble,
    delete: deleteBubble,
    reorder: reorderBubble,
    sequence: sequenceBubble,
    link: linkBubble,
    unlink: unlinkBubble,
    toggleSfx,
    dragStart,
    dragEnd,
    resetPosition: resetBubblePosition,
    inflateMargin,
    openContextMenu,
  }), [
    selectBubble,
    updateBubble,
    deleteBubble,
    reorderBubble,
    sequenceBubble,
    linkBubble,
    unlinkBubble,
    toggleSfx,
    dragStart,
    dragEnd,
    resetBubblePosition,
    inflateMargin,
    openContextMenu,
  ]);
}
