import { useEffect, useRef } from 'react';
import { clientApi, getServerUrl } from '../api/bridge.js';
import {
  getBubbleText,
  getBubbleTranslation,
  getBubbleAiTranslation,
} from '../utils/bubbleNormalizer.js';

const _prefetchedPageDataMap = new Map();
const _PREFETCH_TTL_MS = 12000;
const _PREFETCH_MAX_ENTRIES = 12;

export function prefetchPageData(path) {
  if (!path || typeof clientApi?.get_page_data !== 'function') return;
  const now = Date.now();
  const existing = _prefetchedPageDataMap.get(path);
  if (existing && now - existing.ts < _PREFETCH_TTL_MS) return;

  const promise = Promise.resolve(clientApi.get_page_data(path)).catch(() => null);
  _prefetchedPageDataMap.set(path, { ts: now, promise });
  while (_prefetchedPageDataMap.size > _PREFETCH_MAX_ENTRIES) {
    const oldestKey = _prefetchedPageDataMap.keys().next().value;
    _prefetchedPageDataMap.delete(oldestKey);
  }
}

function consumePrefetchedPageData(path, refreshTrigger) {
  if (!path || refreshTrigger) {
    if (path) _prefetchedPageDataMap.delete(path);
    return null;
  }
  const entry = _prefetchedPageDataMap.get(path);
  if (!entry) return null;
  _prefetchedPageDataMap.delete(path);
  if (Date.now() - entry.ts > _PREFETCH_TTL_MS) return null;
  return entry.promise;
}

/**
 * Hook modular responsável pelo carregamento assíncrono de imagem,
 * fallback para Base64 e recuperação de metadados OCR/Layout da página ativa.
 */
export function useSeamlessDataLoader({
  page,
  refreshTrigger,
  bgImage,
  history,
  tools,
  setActiveBubbleId,
  setIsViewOnlyMode,
  setSaveStatus,
  setBgImage,
  setBgSize,
  fitImageToContainer,
  setOcrDataRaw,
  hasBoxesRef,
}) {
  const lastLoadedImageRef = useRef(null);
  const activeImgElementRef = useRef(null);

  // Efeito de desmontagem: liberação imediata de memória de textura da GPU no Chromium
  useEffect(() => {
    return () => {
      if (activeImgElementRef.current) {
        try {
          activeImgElementRef.current.onload = null;
          activeImgElementRef.current.onerror = null;
          activeImgElementRef.current.src = '';
        } catch (_) {}
        activeImgElementRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const dn = page?.path;
    if (!dn) return;

    let isCancelled = false;
    let img = null;

    const isPathChange = lastLoadedImageRef.current !== dn;
    if (isPathChange) {
      if (activeImgElementRef.current) {
        try {
          activeImgElementRef.current.onload = null;
          activeImgElementRef.current.onerror = null;
          activeImgElementRef.current.src = '';
        } catch (_) {}
        activeImgElementRef.current = null;
      }
      if (history?.clearHistory) history.clearHistory();
      if (tools?.resetTools) tools.resetTools();
      if (setActiveBubbleId) setActiveBubbleId(null);
      if (setBgImage) setBgImage(null);
    }

    if (setIsViewOnlyMode) setIsViewOnlyMode(false);
    if (setSaveStatus) setSaveStatus('saved');

    try {
      const serverUrl = getServerUrl ? getServerUrl() : 'http://127.0.0.1:5000';
      const cacheBust = refreshTrigger ? `&_t=${refreshTrigger}` : '';
      const url = `${serverUrl}/api/image?path=${encodeURIComponent(dn)}${cacheBust}`;

      if (isPathChange || !bgImage || refreshTrigger) {
        img = new window.Image();
        img.crossOrigin = 'anonymous';

        const applyLoadedImage = (loadedImg) => {
          if (isCancelled || !loadedImg) return;
          if (activeImgElementRef.current && activeImgElementRef.current !== loadedImg) {
            try {
              activeImgElementRef.current.onload = null;
              activeImgElementRef.current.onerror = null;
              activeImgElementRef.current.src = '';
            } catch (_) {}
          }
          activeImgElementRef.current = loadedImg;
          lastLoadedImageRef.current = dn;
          const iw = loadedImg.naturalWidth || loadedImg.width;
          const ih = loadedImg.naturalHeight || loadedImg.height;
          if (fitImageToContainer) {
            fitImageToContainer(iw, ih);
          }
          if (setBgImage) setBgImage(loadedImg);
          if (setBgSize) setBgSize({ width: iw, height: ih });

          // Notifica que a imagem do estúdio foi decodificada e renderizada com sucesso no Canvas
          if (typeof window !== 'undefined') {
            window.__VISIONARY_CANVAS_PAGE_READY__ = dn;
            // Aguarda dois frames para garantir que o Konva e o React pintaram o buffer na tela
            requestAnimationFrame(() => {
              requestAnimationFrame(() => {
                window.dispatchEvent(new CustomEvent('visionary:page-image-loaded', { detail: { path: dn } }));
              });
            });
          }
        };

        img.onload = () => applyLoadedImage(img);

        img.onerror = async () => {
          if (!isCancelled) {
            try {
              const res = await clientApi.get_image_base64_full(dn);
              if (res && res.success && !isCancelled && res.data_url) {
                const fbImg = new window.Image();
                fbImg.onload = () => applyLoadedImage(fbImg);
                fbImg.src = res.data_url;
                if (fbImg.complete && fbImg.naturalWidth > 0) {
                  applyLoadedImage(fbImg);
                }
                return;
              }
            } catch (e) {
              console.error('Falha ao carregar fallback da imagem', e);
            }
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('visionary:page-image-loaded', { detail: { path: dn, failed: true } }));
            }
          }
        };

        img.src = url;

        if (img.complete && (img.naturalWidth > 0 || img.width > 0)) {
          applyLoadedImage(img);
        }
      }

      const pageDataPromise =
        consumePrefetchedPageData(dn, refreshTrigger) || clientApi.get_page_data(dn);

      pageDataPromise
        .then((res) => {
          if (isCancelled) return;
          if (res && res.success && res.has_data) {
            const parsed = res.cards.map((e) => ({
              ...e,
              text: getBubbleText({ ...e, text: e.original ?? e.text }),
              translated: getBubbleTranslation(e),
              ai_translated: getBubbleAiTranslation(e),
              user_edited: !!e.user_edited,
              label: e.label || 'text_tool',
              is_bubble: e.is_bubble === undefined ? e.label && e.label.includes('bubble') : e.is_bubble,
              initial_box: Array.isArray(e.initial_box) && e.initial_box.length === 4
                ? e.initial_box
                : [e.x1, e.y1, e.x2, e.y2],
              initial_polygon: Array.isArray(e.initial_polygon) && e.initial_polygon.length > 0
                ? e.initial_polygon
                : (Array.isArray(e.polygon) ? e.polygon : []),
            }));
            parsed.sort((a, b) => a.order - b.order || a.y1 - b.y1);
            if (setOcrDataRaw) setOcrDataRaw({ boxes: parsed, panels: res.panels || [] });
            if (hasBoxesRef) hasBoxesRef.current = parsed.length > 0;
            if (res.is_backup && setIsViewOnlyMode) setIsViewOnlyMode(true);
          } else {
            if (setOcrDataRaw) setOcrDataRaw({ boxes: [], panels: res?.panels || [] });
            if (hasBoxesRef) hasBoxesRef.current = false;
          }
        })
        .catch((err) => {
          console.error('Erro ao carregar dados:', err);
          if (!isCancelled) {
            if (setOcrDataRaw) setOcrDataRaw({ boxes: [], panels: [] });
            if (hasBoxesRef) hasBoxesRef.current = false;
          }
        });
    } catch (e) {
      console.error('Erro no carregamento', e);
      if (!isCancelled) {
        if (setOcrDataRaw) setOcrDataRaw({ boxes: [], panels: [] });
        if (hasBoxesRef) hasBoxesRef.current = false;
      }
    }

    return () => {
      isCancelled = true;
      if (img) {
        img.onload = null;
        img.onerror = null;
        try {
          img.src = '';
        } catch (_) {}
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Executa apenas na troca de página ou refreshTrigger para evitar loops ao atualizar bgImage
  }, [page?.path, refreshTrigger]);

  return { lastLoadedImageRef };
}
