import { useState, useCallback, useRef, useEffect } from "react";
import { copyTextToClipboard } from "../utils/clipboard";
import { playCopySound } from "../utils/sound";
import { useLibraryStore, safeSetStorageItem } from "../stores/useLibraryStore";

/**
 * Hook para operações de cópia de balões, páginas completas e texto bruto,
 * persistência do estado de progresso de balões copiados e feedback audiovisual.
 */
export function useLibraryClipboard({
  activeFile,
  fileContent,
  applyTypographyRules,
  addToast,
}) {
  const copiedBlocks = useLibraryStore((s) => s.copiedBlocks);
  const setCopiedBlocks = useLibraryStore((s) => s.setCopiedBlocks);
  const setActiveCopiedId = useLibraryStore((s) => s.setActiveCopiedId);

  const [lastCopiedId, setLastCopiedId] = useState(null);
  const [isRawCopied, setIsRawCopied] = useState(false);

  const copyBalloon = useCallback(async (id, data) => {
    let textToCopy = "";
    let isEnglishFallback = false;

    if (data && typeof data === "object") {
      if (data.br && data.br !== "[PENDENTE]") {
        textToCopy = data.br;
      } else if (data.en && data.en !== "[Sem texto original detectado]") {
        textToCopy = data.en;
        isEnglishFallback = true;
      }
    } else if (typeof data === "string") {
      textToCopy = data === "[PENDENTE]" ? "" : data;
    }

    textToCopy = typeof textToCopy === "string" ? textToCopy : String(textToCopy || "");

    if (!textToCopy.trim()) {
      addToast?.("Balão sem texto disponível para copiar.", "warning");
      return;
    }

    try {
      const formattedText = typeof applyTypographyRules === "function"
        ? applyTypographyRules(textToCopy)
        : textToCopy;

      const success = await copyTextToClipboard(formattedText);
      if (!success) {
        addToast?.("Erro ao acessar a área de transferência.", "error");
        return;
      }

      setLastCopiedId(id);
      setActiveCopiedId(id);
      setCopiedBlocks((prev) => {
        const next = { ...prev, [id]: true };
        if (activeFile?.path) {
          safeSetStorageItem(`visionary:copied_${activeFile.path}`, JSON.stringify(next), "visionary:copied_");
        }
        return next;
      });

      playCopySound();
      if (isEnglishFallback) {
        addToast?.("Texto original (EN) copiado para o Photoshop!", "info");
      } else {
        addToast?.("Balão copiado para o Photoshop!", "success");
      }
    } catch (err) {
      addToast?.(`Erro ao copiar: ${err?.message || err}`, "error");
    }
  }, [activeFile, applyTypographyRules, setCopiedBlocks, setActiveCopiedId, addToast]);

  const undoCopyBalloon = useCallback((id) => {
    if (!id) return;
    setCopiedBlocks((prev) => {
      const next = { ...prev };
      delete next[id];
      if (activeFile?.path) {
        safeSetStorageItem(`visionary:copied_${activeFile.path}`, JSON.stringify(next), "visionary:copied_");
      }
      return next;
    });
    addToast?.("Status de colado desfeito!", "info");
  }, [activeFile, setCopiedBlocks, addToast]);

  const copyFullPage = useCallback(async (page) => {
    if (!page || !Array.isArray(page.balloons)) return;

    const texts = page.balloons
      .map((b) => (b.br && b.br !== "[PENDENTE]" ? b.br : b.en && b.en !== "[Sem texto original detectado]" ? b.en : ""))
      .filter(Boolean)
      .map((t) => (typeof applyTypographyRules === "function" ? applyTypographyRules(t) : t));

    if (texts.length === 0) {
      addToast?.("Nenhum texto disponível para copiar nesta página.", "warning");
      return;
    }

    try {
      const success = await copyTextToClipboard(texts.join("\n\n"));
      if (!success) {
        addToast?.("Erro ao acessar a área de transferência.", "error");
        return;
      }

      const nextCopied = { ...copiedBlocks };
      page.balloons.forEach((_, idx) => {
        nextCopied[`${page.pageNumber}-${idx}`] = true;
      });
      setCopiedBlocks(nextCopied);

      if (activeFile?.path) {
        safeSetStorageItem(`visionary:copied_${activeFile.path}`, JSON.stringify(nextCopied), "visionary:copied_");
      }

      playCopySound();
      addToast?.(`Página ${page.pageNumber} copiada (${texts.length} balões)!`, "success");
    } catch (err) {
      addToast?.(`Erro ao copiar página: ${err?.message || err}`, "error");
    }
  }, [copiedBlocks, activeFile, applyTypographyRules, setCopiedBlocks, addToast]);

  const copyRawContent = useCallback(async () => {
    if (!fileContent) return;
    try {
      const success = await copyTextToClipboard(fileContent);
      if (!success) {
        addToast?.("Erro ao acessar a área de transferência.", "error");
        return;
      }
      setIsRawCopied(true);
      playCopySound();
      addToast?.("Roteiro copiado para a área de transferência!", "success");
      setTimeout(() => setIsRawCopied(false), 2000);
    } catch (err) {
      addToast?.(`Erro ao copiar roteiro: ${err?.message || err}`, "error");
    }
  }, [fileContent, addToast]);

  const resetConfirmTimerRef = useRef(null);
  const resetPendingRef = useRef(false);

  useEffect(() => {
    return () => {
      if (resetConfirmTimerRef.current) clearTimeout(resetConfirmTimerRef.current);
    };
  }, []);

  const resetProgress = useCallback(
    (force = false) => {
      if (!activeFile) return;

      if (!force && !resetPendingRef.current) {
        resetPendingRef.current = true;
        addToast?.("Clique novamente para confirmar a redefinição do progresso.", "warning");
        if (resetConfirmTimerRef.current) clearTimeout(resetConfirmTimerRef.current);
        resetConfirmTimerRef.current = setTimeout(() => {
          resetPendingRef.current = false;
        }, 4000);
        return;
      }

      if (resetConfirmTimerRef.current) {
        clearTimeout(resetConfirmTimerRef.current);
        resetConfirmTimerRef.current = null;
      }
      resetPendingRef.current = false;
      setCopiedBlocks({});
      try {
        localStorage.removeItem(`visionary:copied_${activeFile.path}`);
      } catch (err) {
        console.warn("[useLibraryClipboard] Falha ao limpar localStorage:", err);
      }
      addToast?.("Progresso redefinido com sucesso!", "info");
    },
    [activeFile, setCopiedBlocks, addToast]
  );

  return {
    lastCopiedId,
    setLastCopiedId,
    isRawCopied,
    copyBalloon,
    undoCopyBalloon,
    copyFullPage,
    copyRawContent,
    resetProgress,
  };
}
