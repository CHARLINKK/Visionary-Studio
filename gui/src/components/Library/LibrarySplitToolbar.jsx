import React from "react";
import { ZoomIn, ZoomOut, Maximize, Crosshair, Eye } from "lucide-react";
import { useLibraryViewerStore } from "../../stores/useLibraryViewerStore";

export default function LibrarySplitToolbar() {
  const zoomScale = useLibraryViewerStore((s) => s.zoomScale);
  const setZoomScale = useLibraryViewerStore((s) => s.setZoomScale);
  const resetZoom = useLibraryViewerStore((s) => s.resetZoom);
  const autoZoomEnabled = useLibraryViewerStore((s) => s.autoZoomEnabled);
  const setAutoZoomEnabled = useLibraryViewerStore((s) => s.setAutoZoomEnabled);
  const showMarkers = useLibraryViewerStore((s) => s.showMarkers);
  const setShowMarkers = useLibraryViewerStore((s) => s.setShowMarkers);
  const hideEnglish = useLibraryViewerStore((s) => s.hideEnglish);
  const setHideEnglish = useLibraryViewerStore((s) => s.setHideEnglish);

  return (
    <>
      <button
        type="button"
        className="btn-split-tool"
        onClick={() => setZoomScale((s) => Math.max(0.2, s - 0.2))}
        title="Reduzir Zoom"
      >
        <ZoomOut size={12} />
      </button>
      <button
        type="button"
        className="btn-split-tool zoom-val"
        onClick={resetZoom}
        title="Redefinir Zoom para 100%"
      >
        {Math.round(zoomScale * 100)}%
      </button>
      <button
        type="button"
        className="btn-split-tool"
        onClick={() => setZoomScale((s) => Math.min(8, s + 0.2))}
        title="Aumentar Zoom"
      >
        <ZoomIn size={12} />
      </button>
      <button
        type="button"
        className="btn-split-tool reset"
        onClick={resetZoom}
        title="Centralizar e ajustar tela inteira"
      >
        <Maximize size={12} />
      </button>

      <button
        type="button"
        className={`btn-split-tool ${autoZoomEnabled ? "active" : ""}`}
        onClick={() => setAutoZoomEnabled(!autoZoomEnabled)}
        title={"Auto-Zoom (Z)\nAproxima automaticamente o balão selecionado"}
      >
        <Crosshair size={12} />
      </button>
      <button
        type="button"
        className={`btn-split-tool ${showMarkers ? "active" : ""}`}
        onClick={() => setShowMarkers(!showMarkers)}
        title="Mostrar marcações numeradas na imagem"
      >
        <Eye size={12} />
      </button>
      <button
        type="button"
        className={`btn-split-tool ${!hideEnglish ? "active" : ""}`}
        onClick={() => setHideEnglish(!hideEnglish)}
        title="Mostrar linha com o texto em inglês (EN:) abaixo da tradução"
      >
        <span style={{ fontSize: 10, fontWeight: 700 }}>EN</span>
      </button>
    </>
  );
}
