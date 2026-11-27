import { useState, useRef, useEffect, useCallback } from 'react';

/**
 * Hook modular para gerenciamento da dimensão do palco (Stage),
 * imagem de fundo e redimensionamento dinâmico responsivo (ResizeObserver).
 */
export function useSeamlessStage({
  containerRef: externalContainerRef,
  bgImage: externalBgImage,
  setBgImage: externalSetBgImage,
  bgSize: externalBgSize,
  setBgSize: externalSetBgSize,
  hasUserAdjustedZoomRef,
  zoomStateRef,
  setZoomScale,
  setZoomStagePos,
} = {}) {
  const [internalBgImage, internalSetBgImage] = useState(null);
  const [internalBgSize, internalSetBgSize] = useState({ width: 800, height: 1200 });
  const [stageSize, setStageSize] = useState({ width: 1200, height: 800 });
  const internalContainerRef = useRef(null);

  const containerRef = externalContainerRef || internalContainerRef;
  const bgImage = externalBgImage !== undefined ? externalBgImage : internalBgImage;
  const setBgImage = externalSetBgImage || internalSetBgImage;
  const bgSize = externalBgSize !== undefined ? externalBgSize : internalBgSize;
  const setBgSize = externalSetBgSize || internalSetBgSize;

  const fitImageToContainer = useCallback((iw, ih) => {
    const el = containerRef.current;
    if (!el || iw <= 0 || ih <= 0) return;
    const cw = el.offsetWidth;
    const ch = el.offsetHeight;
    if (cw > 0 && ch > 0) {
      const newScale = Math.max(0.1, Math.min((cw - 80) / iw, (ch - 80) / ih));
      const newPos = {
        x: (cw - iw * newScale) / 2,
        y: (ch - ih * newScale) / 2,
      };
      setStageSize({ width: cw, height: ch });
      if (setZoomScale) setZoomScale(newScale);
      if (setZoomStagePos) setZoomStagePos(newPos);
      if (zoomStateRef) {
        zoomStateRef.current = { scale: newScale, position: newPos };
      }
    }
  }, [containerRef, setZoomScale, setZoomStagePos, zoomStateRef]);

  // Observer de redimensionamento dinâmico: adapta o Stage ao tamanho exato do container e centraliza a página
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const updateStageDimensions = () => {
      const cw = el.offsetWidth;
      const ch = el.offsetHeight;
      if (cw > 0 && ch > 0) {
        setStageSize((prev) => {
          if (prev.width === cw && prev.height === ch) return prev;
          return { width: cw, height: ch };
        });

        if (!hasUserAdjustedZoomRef?.current && bgImage) {
          const iw = bgImage.naturalWidth || bgImage.width || bgSize.width;
          const ih = bgImage.naturalHeight || bgImage.height || bgSize.height;
          fitImageToContainer(iw, ih);
        }
      }
    };

    updateStageDimensions();

    let ro = null;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => {
        updateStageDimensions();
      });
      ro.observe(el);
    } else {
      window.addEventListener('resize', updateStageDimensions);
    }

    return () => {
      if (ro) ro.disconnect();
      else window.removeEventListener('resize', updateStageDimensions);
    };
  }, [containerRef, bgImage, bgSize, fitImageToContainer, hasUserAdjustedZoomRef]);

  // Garantia de auto-ajuste e centralização assim que bgImage ou bgSize ficarem disponíveis
  useEffect(() => {
    if (!bgImage || hasUserAdjustedZoomRef?.current) return;
    const iw = bgImage.naturalWidth || bgImage.width || bgSize.width;
    const ih = bgImage.naturalHeight || bgImage.height || bgSize.height;
    if (iw > 0 && ih > 0) {
      const rafId = requestAnimationFrame(() => {
        fitImageToContainer(iw, ih);
      });
      return () => cancelAnimationFrame(rafId);
    }
  }, [bgImage, bgSize, fitImageToContainer, hasUserAdjustedZoomRef]);

  // Sincronização ao receber eventos de layout pronto ou redimensionamento da janela
  useEffect(() => {
    const handleRecalculate = () => {
      requestAnimationFrame(() => {
        const el = containerRef.current;
        if (!el) return;
        const cw = el.offsetWidth;
        const ch = el.offsetHeight;
        if (cw > 0 && ch > 0) {
          setStageSize({ width: cw, height: ch });
          if (bgImage && !hasUserAdjustedZoomRef?.current) {
            const iw = bgImage.naturalWidth || bgImage.width || bgSize.width;
            const ih = bgImage.naturalHeight || bgImage.height || bgSize.height;
            fitImageToContainer(iw, ih);
          }
        }
      });
    };

    window.addEventListener('visionary:app-ready', handleRecalculate);
    window.addEventListener('resize', handleRecalculate);
    return () => {
      window.removeEventListener('visionary:app-ready', handleRecalculate);
      window.removeEventListener('resize', handleRecalculate);
    };
  }, [containerRef, bgImage, bgSize, fitImageToContainer, hasUserAdjustedZoomRef]);

  return {
    bgImage,
    setBgImage,
    bgSize,
    setBgSize,
    stageSize,
    setStageSize,
    containerRef,
    fitImageToContainer,
  };
}
