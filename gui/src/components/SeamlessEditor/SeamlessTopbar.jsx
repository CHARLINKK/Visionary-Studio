import {
  useSeamlessDoc,
  useSeamlessViewport,
  useSeamlessUi,
} from "../../contexts/SeamlessContext";
import React from "react";
import {
  ChevronLeft, ChevronRight, Undo, LayoutDashboard, ScanText, Languages,
  Loader2, AlertCircle, CheckCircle, Maximize, Crosshair
} from "lucide-react";

const SeamlessTopbar = React.memo(function SeamlessTopbar({
  onNavigate, pageIndex, totalPages, page, showDebugPanels, viewMode, setViewMode,
  canEditLayout, canEditOcr, canEditTranslation, saveStatus, onRetrySave,
  toggleAutoZoom, fitToScreen, scale, autoZoom,
}) {
  return (
    <div className="editor-topbar">
      <div className="topbar-left">
        {onNavigate && (
          <div className="page-nav">
            <button
              type="button"
              className="btn-icon"
              onClick={() => onNavigate(-1)}
              disabled={pageIndex === 0}
              title="Página anterior"
            >
              <ChevronLeft size={16} />
            </button>
            <div className="page-count">
              {pageIndex + 1} / {totalPages}
            </div>
            <button
              type="button"
              className="btn-icon"
              onClick={() => onNavigate(1)}
              disabled={pageIndex === totalPages - 1}
              title="Próxima página"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
        <div
          className="editor-title"
          style={{
            marginLeft: "12px",
            display: "flex",
            alignItems: "center",
          }}
        >
          {page?.name || "Página Desconhecida"}
          {showDebugPanels && (
            <Undo
              size={14}
              style={{ marginLeft: "8px", color: "#60a5fa", opacity: 0.8 }}
              title="Esta página possui um Ponto de Restauração salvo"
            />
          )}
        </div>
      </div>

      <div className="mode-toggles">
        <div
          className={`mode-btn ${viewMode === "view" ? "active" : ""}`}
          onClick={() => setViewMode("view")}
        >
          Visualizar
        </div>
        {canEditLayout && (
          <div
            className={`mode-btn ${viewMode === "layout" ? "active" : ""}`}
            onClick={() => setViewMode("layout")}
            title="Modo Layout (1)"
          >
            <LayoutDashboard size={15} /> Layout
          </div>
        )}
        {canEditOcr && (
          <div
            className={`mode-btn ${viewMode === "ocr" ? "active" : ""}`}
            onClick={() => setViewMode("ocr")}
            title="Modo OCR (2)"
          >
            <ScanText size={15} /> OCR
          </div>
        )}
        {canEditTranslation && (
          <div
            className={`mode-btn ${viewMode === "translation" ? "active" : ""}`}
            onClick={() => setViewMode("translation")}
            title="Modo Tradução (3)"
          >
            <Languages size={15} /> Tradução
          </div>
        )}
      </div>

      <div
        className="topbar-right"
        style={{ display: "flex", alignItems: "center", gap: "8px" }}
      >
        <div
          className="autosave-status-badge"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "5px",
            fontSize: "11px",
            color: "var(--text-muted)",
            marginRight: "4px",
          }}
          title="Status do salvamento automático"
        >
          {saveStatus === "saving" ? (
            <>
              <Loader2
                size={12}
                className="spin"
                style={{ color: "#38bdf8" }}
              />
              <div style={{ color: "#38bdf8" }}>Salvando...</div>
            </>
          ) : saveStatus === "unsaved" ? (
            <>
              <Loader2
                size={12}
                className="spin"
                style={{ color: "#f59e0b" }}
              />
              <div style={{ color: "#f59e0b" }}>Não salvo...</div>
            </>
          ) : saveStatus === "error" ? (
            <button
              type="button"
              className="autosave-retry-btn"
              onClick={() => onRetrySave?.()}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                background: "rgba(239, 68, 68, 0.15)",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                borderRadius: "4px",
                padding: "2px 6px",
                color: "#ef4444",
                cursor: "pointer",
                fontSize: "11px",
              }}
              title="Clique para tentar salvar novamente"
            >
              <AlertCircle size={12} />
              <span>Erro ao salvar · Repetir</span>
            </button>
          ) : (
            <>
              <CheckCircle size={12} style={{ color: "#10b981" }} />
              <div style={{ color: "var(--text-muted)" }}>Salvo</div>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={fitToScreen}
          className="btn-topbar-tool"
          title="Ajustar Imagem à Tela (Redefinir Zoom)"
        >
          <Maximize size={13} />
          <span className="tool-label">
            Ajustar ({Math.round(scale * 100)}%)
          </span>
        </button>
        <button
          type="button"
          onClick={() => toggleAutoZoom()}
          className={`btn-topbar-tool ${autoZoom ? "active" : ""}`}
          title={
            autoZoom
              ? "Auto-Zoom ATIVADO: aproxima e centraliza o balão ao selecioná-lo (Clique ou tecla Z para alternar)"
              : "Auto-Zoom DESATIVADO: mantém o zoom atual ao selecionar balão (Clique ou tecla Z para alternar)"
          }
        >
          <Crosshair size={14} />
          <span className="tool-label">Auto-Zoom</span>
          <span className="indicator-dot" />
        </button>
      </div>
    </div>
  );
});

export default function SeamlessTopbarContainer() {
  const {
    onNavigate, pageIndex, totalPages, page, viewMode, setViewMode,
    canEditLayout, canEditOcr, canEditTranslation, saveStatus, backend,
  } = useSeamlessDoc();
  const { showDebugPanels } = useSeamlessUi();
  const { zoom } = useSeamlessViewport();
  const { toggleAutoZoom, fitToScreen, scale, autoZoom } = zoom;

  return (
    <SeamlessTopbar
      onNavigate={onNavigate} pageIndex={pageIndex} totalPages={totalPages} page={page}
      showDebugPanels={showDebugPanels} viewMode={viewMode} setViewMode={setViewMode}
      canEditLayout={canEditLayout} canEditOcr={canEditOcr} canEditTranslation={canEditTranslation}
      saveStatus={saveStatus} onRetrySave={backend?.savePageLayout} toggleAutoZoom={toggleAutoZoom}
      fitToScreen={fitToScreen} scale={scale} autoZoom={autoZoom}
    />
  );
}
