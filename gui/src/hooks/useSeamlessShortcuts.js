import { useEffect, useRef } from "react";
import { useWorkspaceStore } from "../stores/useWorkspaceStore";
import {
  reindexBubbleOrders,
  getBubbleGroupId,
  stripBubbleGroupId,
  toggleBubbleSfxState,
} from "../utils/bubbleNormalizer";

export function useSeamlessShortcuts(props) {
  // Ref sempre atualizado no render evita re-registrar o listener global de keydown
  // a cada mudança de estado do editor.
  const latestRef = useRef(props);
  useEffect(() => {
    latestRef.current = props;
  });

  useEffect(() => {
    const handleKeyDown = (e) => {
      const p = latestRef.current;
      if (useWorkspaceStore.getState().activeTab !== "processamento") return;

      const isTyping =
        e.target?.isContentEditable ||
        ["INPUT", "TEXTAREA", "SELECT"].includes(e.target?.tagName);
      if (isTyping) return;

      const isModalOpen = Boolean(
        document.querySelector(
          '.visionary-dialog-overlay, .log-drawer-overlay, .onboarding-overlay, .dev-pwd-overlay, .dev-loading-screen, .lightbox-quicklook-overlay'
        ) ||
        document.body.classList.contains('help-inspector-active')
      );
      if (isModalOpen) return;

      // Comandos com Ctrl / Cmd
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        p.savePageLayout?.();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        p.handleUndo?.();
        return;
      }
      if (
        ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "z")
      ) {
        e.preventDefault();
        p.handleRedo?.();
        return;
      }

      if (e.ctrlKey || e.altKey || e.metaKey) return;

      // Cancelar ou desmarcar seleção (Escape)
      if (e.key === "Escape") {
        if (p.bubbleEditMode === "nodes" || p.bubbleEditMode === "raw" || p.bubbleEditMode === "polygon") {
          p.setBubbleEditMode?.("box");
          return;
        }
        p.setActiveBubbleId?.(null);
        p.setPenPoints?.([]);
        p.setDrawingRect?.(null);
        p.setDragStartPos?.(null);
        p.setRectStartPos?.(null);
        p.setBubbles?.([]);
        if (p.viewMode === "layout") p.setActiveTool?.("select");
        return;
      }

      // Auto-zoom e enquadrar tela
      if (e.key.toLowerCase() === "z") {
        e.preventDefault();
        p.toggleAutoZoom?.();
        return;
      }
      if (e.key.toLowerCase() === "f" || e.key === "0") {
        e.preventDefault();
        p.fitToScreen?.();
        return;
      }

      // Modos de edição (1: Layout, 2: OCR, 3: Tradução)
      if (e.key === "1") {
        if (!p.isViewOnlyMode) p.setViewMode?.("layout");
        return;
      }
      if (e.key === "2") {
        if (p.canEditOcr) p.setViewMode?.("ocr");
        return;
      }
      if (e.key === "3") {
        if (p.canEditTranslation) p.setViewMode?.("translation");
        return;
      }

      // Ferramentas do canvas (ativam e mudam para Layout se necessário)
      const ensureLayoutAndRun = (action) => {
        if (p.viewMode !== "layout" && !p.isViewOnlyMode) {
          p.setViewMode?.("layout");
        }
        action();
      };

      if (e.key.toLowerCase() === "v") {
        ensureLayoutAndRun(() => {
          p.setActiveTool?.("select");
          p.setDragStartPos?.(null);
          p.setRectStartPos?.(null);
        });
        return;
      }
      if (e.key.toLowerCase() === "p") {
        ensureLayoutAndRun(() => {
          p.setActiveTool?.("pen");
          p.setDragStartPos?.(null);
          p.setPenPoints?.([]);
          p.setRectStartPos?.(null);
        });
        return;
      }
      if (e.key.toLowerCase() === "b") {
        ensureLayoutAndRun(() => {
          p.setActiveTool?.("rect");
          p.setDragStartPos?.(null);
          p.setActiveBubbleId?.(null);
          p.setDrawingRect?.(null);
          p.setRectStartPos?.(null);
        });
        return;
      }
      if (e.key.toLowerCase() === "r") {
        ensureLayoutAndRun(() => {
          p.setActiveTool?.("reorder");
          p.setActiveBubbleId?.(null);
          p.setSelectedBubbleIndex?.(0);
          p.setRectStartPos?.(null);
        });
        return;
      }
      if (e.key.toLowerCase() === "l") {
        ensureLayoutAndRun(() => {
          p.setActiveTool?.("link");
          p.setActiveBubbleId?.(null);
          p.setDragStartPos?.(null);
          p.setRectStartPos?.(null);
          p.setBubbles?.([]);
        });
        return;
      }
      if (e.key.toLowerCase() === "s") {
        ensureLayoutAndRun(() => {
          if (p.activeBubbleId != null) {
            p.setOcrData?.((data) => {
              if (!data?.boxes) return data;
              if (p.pushHistory) p.pushHistory(data);
              const updatedBoxes = data.boxes.map((b) =>
                b.id === p.activeBubbleId ? toggleBubbleSfxState(b) : b
              );
              return {
                ...data,
                boxes: reindexBubbleOrders(updatedBoxes),
              };
            });
            p.addToast?.("Balão alternado (Fala ⇄ SFX)", "info");
          } else {
            p.setActiveTool?.("sfx");
            p.setDragStartPos?.(null);
            p.setRectStartPos?.(null);
            p.setBubbles?.([]);
          }
        });
        return;
      }

      // Exclusão do balão selecionado (Del / Backspace)
      if ((e.key === "Delete" || e.key === "Backspace") && p.activeBubbleId != null) {
        e.preventDefault();
        if (p.pushHistory && p.ocrData) p.pushHistory(p.ocrData);
        p.setOcrData?.((data) => {
          const next = { ...data };
          if (next.boxes) {
            const groupId = getBubbleGroupId(
              next.boxes.find((b) => b.id === p.activeBubbleId),
            );
            let filtered = next.boxes.filter((b) => b.id !== p.activeBubbleId);
            if (
              groupId &&
              filtered.filter((b) => getBubbleGroupId(b) === groupId).length === 1
            ) {
              filtered = filtered.map((b) =>
                getBubbleGroupId(b) === groupId ? stripBubbleGroupId(b) : b,
              );
            }
            next.boxes = reindexBubbleOrders(filtered);
          }
          return next;
        });
        p.setActiveBubbleId?.(null);
        p.addToast?.("Balão excluído. Pressione Ctrl+Z para desfazer", "info");
        return;
      }

      // Navegação entre balões (A / D ou ← / →)
      const boxes = p.ocrData?.boxes || [];
      const idx = boxes.findIndex((b) => b.id === p.activeBubbleId);
      if (boxes.length > 0) {
        if (e.key.toLowerCase() === "a" || e.key === "ArrowLeft") {
          e.preventDefault();
          if (idx > 0) {
            p.zoomToSpecificBubble?.(boxes[idx - 1].id);
          } else if (idx === -1) {
            p.zoomToSpecificBubble?.(boxes[0].id);
          } else if (idx === 0) {
            p.zoomToSpecificBubble?.(boxes[boxes.length - 1].id);
          }
          return;
        }
        if (e.key.toLowerCase() === "d" || e.key === "ArrowRight") {
          e.preventDefault();
          if (idx < boxes.length - 1 && idx !== -1) {
            p.zoomToSpecificBubble?.(boxes[idx + 1].id);
          } else if (idx === -1) {
            p.zoomToSpecificBubble?.(boxes[0].id);
          } else if (idx === boxes.length - 1) {
            p.zoomToSpecificBubble?.(boxes[0].id);
          }
          return;
        }
      }

      // Navegação entre páginas (PageUp / PageDown, [ / ] ou ↑ / ↓)
      if (p.onNavigate) {
        if (e.key === "PageUp" || e.key === "ArrowUp" || e.key === "[") {
          e.preventDefault();
          if (p.pageIndex > 0) p.onNavigate(-1);
          return;
        }
        if (e.key === "PageDown" || e.key === "ArrowDown" || e.key === "]") {
          e.preventDefault();
          if (p.pageIndex < p.totalPages - 1) p.onNavigate(1);
          return;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);
}
