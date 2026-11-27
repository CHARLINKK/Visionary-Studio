import { useEffect, useMemo, useCallback } from "react";
import { clientApi, getServerUrl } from "../api/bridge";
import {
  isBubbleSfx,
  getBubbleText,
  getBubbleTranslation,
} from "../utils/bubbleNormalizer";

/**
 * Filtra e ordena os balões para exibição nos cards do modo dividido (Split View).
 * 
 * REGRAS DE NEGÓCIO DO VISIONARY:
 * 1. Exclusão de Onomatopeias (SFX): Efeitos sonoros desenhados na arte não devem poluir a lista de falas.
 * 2. Exclusão de [DELETE]: Balões apagados pelo usuário no Estúdio são ignorados na Biblioteca.
 * 3. Ordenação Japonesa de Leitura: Prioriza a propriedade 'order' (definida da direita para a esquerda)
 *    ou a coordenada vertical (y1) como fallback.
 */
function filterAndSortSplitCards(rawCards) {
  if (!Array.isArray(rawCards)) return [];
  return rawCards
    .filter((c) => {
      if (isBubbleSfx(c)) return false;
      const orig = getBubbleText(c);
      const trans = getBubbleTranslation(c);
      if (orig.trim() === "[DELETE]" || trans.trim() === "[DELETE]") return false;
      return true;
    })
    .sort((a, b) => (a.order ?? 999) - (b.order ?? 999) || a.y1 - b.y1);
}

/**
 * Sub-hook especializado para o modo Lado a Lado (Split View) da Biblioteca:
 * - Resolução de caminho de imagem e URL de preview
 * - Carregamento assíncrono de coordenadas/cards de cada página via backend (`get_page_data`)
 * - Navegação direta e zoom em um balão específico (`jumpToBalloonInSplit`)
 */
export function useLibrarySplitCards({
  viewMode,
  activeFile,
  activePageData,
  parsedPages,
  activePageIndex,
  setActivePageIndex,
  setActiveBlockId,
  setActiveCopiedId,
  changeViewMode,
  blockInputs,
  setBlockInputs,
  setZoomTargetRect,
}) {
  const resolveImagePath = useCallback((imageName) => {
    if (!activeFile?.path || !imageName) return "";
    const baseDir = (activeFile.chapter_dir || activeFile.path.replace(/[\\/][^\\/]+$/, "")).replace(/\\/g, "/");
    return `${baseDir}/${imageName}`.replace(/\\/g, "/");
  }, [activeFile]);

  const getPreviewUrl = useCallback((imageName) => {
    const path = resolveImagePath(imageName);
    return path ? `${getServerUrl()}/api/image?path=${encodeURIComponent(path)}` : "";
  }, [resolveImagePath]);

  useEffect(() => {
    if (viewMode !== "split" || !activeFile || !activePageData) return;
    const pageName = activePageData.pageName;
    if (blockInputs[pageName]) return;
    const imgPath = resolveImagePath(pageName);
    if (!imgPath) return;
    let isMounted = true;

    (async () => {
      try {
        const res = await clientApi.get_page_data(imgPath);
        if (isMounted && res && res.success && Array.isArray(res.cards)) {
          const cards = filterAndSortSplitCards(res.cards);
          setBlockInputs((prev) => ({ ...prev, [pageName]: cards }));
        }
      } catch (err) {
        console.warn("[Library SplitView] get_page_data error:", err);
      }
    })();
    return () => { isMounted = false; };
  }, [viewMode, activeFile, activePageData, blockInputs, resolveImagePath, setBlockInputs]);

  const currentPageCards = useMemo(
    () => (activePageData && blockInputs[activePageData.pageName]) || [],
    [activePageData, blockInputs]
  );

  const jumpToBalloonInSplit = useCallback(
    (pageNumber, balloonIndex, balloonId) => {
      let targetIndex = null;
      let targetId = null;

      if (typeof balloonIndex === "number") {
        targetIndex = balloonIndex;
        targetId = balloonId != null ? String(balloonId) : null;
      } else if (typeof balloonIndex === "string") {
        targetId = balloonIndex;
      } else if (balloonId != null) {
        targetId = String(balloonId);
      }

      // 1. Localizar página alvo
      const pIdx = parsedPages.findIndex(
        (p) => String(p.pageNumber) === String(pageNumber)
      );
      if (pIdx !== -1) {
        setActivePageIndex(pIdx);
      }

      const targetPage = pIdx !== -1 ? parsedPages[pIdx] : parsedPages[activePageIndex];
      const targetPageNumber = targetPage?.pageNumber || pageNumber || 1;

      // 2. Determinar o índice exato do balão (0-based)
      let bIdx = 0;
      if (targetPage && Array.isArray(targetPage.balloons) && targetPage.balloons.length > 0) {
        if (targetIndex !== null && typeof targetIndex === "number") {
          bIdx = Math.max(0, Math.min(targetIndex, targetPage.balloons.length - 1));
        } else if (targetId !== null) {
          const foundIdx = targetPage.balloons.findIndex(
            (b) => b.id != null && String(b.id) === String(targetId)
          );
          if (foundIdx !== -1) {
            bIdx = foundIdx;
          } else {
            const num = parseInt(targetId, 10);
            if (!isNaN(num) && num >= 1 && num <= targetPage.balloons.length) {
              bIdx = num - 1;
            } else {
              bIdx = 0;
            }
          }
        }
      }

      const key = `${targetPageNumber}-${bIdx}`;
      const targetBalloon = targetPage?.balloons?.[bIdx];

      setActiveBlockId(bIdx);
      setActiveCopiedId(key);
      changeViewMode("split");

      // 3. Zoom no card do balão
      if (targetPage?.pageName) {
        const findAndSetCard = (cards) => {
          if (!Array.isArray(cards) || cards.length === 0) return;
          const match =
            (targetBalloon?.id != null
              ? cards.find((c) => c.id != null && String(c.id) === String(targetBalloon.id))
              : null) || cards[bIdx];
          if (match) {
            setZoomTargetRect(match);
          }
        };

        if (blockInputs[targetPage.pageName]) {
          findAndSetCard(blockInputs[targetPage.pageName]);
        } else {
          const imgPath = resolveImagePath(targetPage.pageName);
          if (imgPath) {
            clientApi
              .get_page_data(imgPath)
              .then((res) => {
                if (res && res.success && Array.isArray(res.cards)) {
                  const cards = filterAndSortSplitCards(res.cards);
                  setBlockInputs((prev) => ({ ...prev, [targetPage.pageName]: cards }));
                  findAndSetCard(cards);
                }
              })
              .catch(() => {});
          }
        }
      }

      // 4. Scroll suave garantido até o balão na lista lateral
      const scrollTarget = () => {
        const el = document.getElementById(`split-balloon-${key}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      };
      setTimeout(scrollTarget, 100);
      setTimeout(scrollTarget, 280);
    },
    [
      parsedPages,
      activePageIndex,
      setActivePageIndex,
      setActiveBlockId,
      setActiveCopiedId,
      changeViewMode,
      blockInputs,
      setBlockInputs,
      setZoomTargetRect,
      resolveImagePath,
    ],
  );

  return {
    resolveImagePath,
    getPreviewUrl,
    currentPageCards,
    jumpToBalloonInSplit,
  };
}
