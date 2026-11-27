import React, { useState, useMemo, useCallback, useContext } from "react";
import { useWorkspaceStore } from "../../stores/useWorkspaceStore";
import { ToastContext } from "../../contexts/ToastContext";
import {
  LayoutDashboard,
  ScanText,
  Languages,
  Terminal,
  AlertTriangle,
  FileText,
  Copy,
  Check,
  Sparkles,
} from "lucide-react";

const SeamlessOverviewInspector = React.memo(function SeamlessOverviewInspector({
  page,
  bgSize = { width: 0, height: 0 },
  canEditLayout = false,
  canEditOcr = false,
  canEditTranslation = false,
  ocrData,
  setIsRestartModalOpen,
  showOcrDebug = false,
  setShowOcrDebug = () => {},
  setViewMode,
  setActiveBubbleId: _setActiveBubbleId,
  zoomToSpecificBubble: _zoomToSpecificBubble,
}) {
  const isDevUnlocked = useWorkspaceStore((s) => s.isDevUnlocked);
  const toast = useContext(ToastContext);
  const addToast = toast?.addToast;

  const [showScriptPreview, setShowScriptPreview] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  React.useEffect(() => {
    if (!isDevUnlocked && showOcrDebug) {
      setShowOcrDebug(false);
    }
  }, [isDevUnlocked, showOcrDebug, setShowOcrDebug]);

  const boxes = useMemo(() => ocrData?.boxes || [], [ocrData?.boxes]);
  const isPending = !canEditLayout && !canEditOcr && !canEditTranslation;

  const dialogueCount = useMemo(() => boxes.filter((b) => !b.is_sfx).length, [boxes]);
  const sfxCount = useMemo(() => boxes.filter((b) => b.is_sfx).length, [boxes]);
  const charCount = useMemo(
    () => boxes.reduce((acc, item) => acc + (item.text ? item.text.length : 0), 0),
    [boxes]
  );
  const transCount = useMemo(
    () => boxes.reduce((acc, item) => acc + (item.translated ? item.translated.length : 0), 0),
    [boxes]
  );

  const handleCopyScript = useCallback(() => {
    const lines = boxes.map((b, idx) => {
      const tag = b.is_sfx ? "[SFX]" : "[Fala]";
      const orig = b.text ? b.text : "(Aguardando OCR)";
      const trans = b.translated ? ` -> ${b.translated}` : "";
      return `#${String(idx + 1).padStart(2, "0")} ${tag}: ${orig}${trans}`;
    });
    const content = `Página: ${page?.name || "Página"}\n${lines.join("\n")}`;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(content).then(() => {
        setIsCopied(true);
        if (addToast) {
          addToast("Roteiro da página copiado!", "success");
        }
        setTimeout(() => setIsCopied(false), 2000);
      }).catch(() => {});
    }
  }, [boxes, page?.name, addToast]);

  return (
    <div className="inspector-section">
      <h4>Visão Geral da Página</h4>
      <div className="inspector-overview-stack">
        <div className="inspector-card inspector-action-card">
          <div className="inspector-action-header">
            <Sparkles size={15} className="inspector-icon-accent" />
            <span className="inspector-card-subtitle" style={{ margin: 0 }}>
              Próximo Passo Recomendado
            </span>
          </div>

          {boxes.length === 0 ? (
            <>
              <p className="inspector-action-desc">
                Nenhum balão delimitado nesta página. Abra o modo Layout para demarcar os diálogos.
              </p>
              {setViewMode && (
                <button
                  type="button"
                  className="inspector-btn-primary"
                  onClick={() => setViewMode("layout")}
                >
                  <LayoutDashboard size={14} /> Abrir Modo Layout para Delimitar
                </button>
              )}
            </>
          ) : !canEditOcr ? (
            <>
              <p className="inspector-action-desc">
                {boxes.length} {boxes.length === 1 ? "balão pronto" : "balões prontos"} para extração óptica de caracteres.
              </p>
              {setViewMode && (
                <button
                  type="button"
                  className="inspector-btn-primary"
                  onClick={() => setViewMode("layout")}
                >
                  <LayoutDashboard size={14} /> Ajustar Ordem no Modo Layout
                </button>
              )}
            </>
          ) : !canEditTranslation ? (
            <>
              <p className="inspector-action-desc">
                Textos originais extraídos. Página pronta para revisão de OCR ou tradução assistida.
              </p>
              {setViewMode && (
                <button
                  type="button"
                  className="inspector-btn-primary"
                  onClick={() => setViewMode("ocr")}
                >
                  <ScanText size={14} /> Ir para Revisão de OCR
                </button>
              )}
            </>
          ) : (
            <>
              <p className="inspector-action-desc">
                Tradução concluída. Página pronta para diagramação ou exportação de roteiro.
              </p>
              {setViewMode && (
                <button
                  type="button"
                  className="inspector-btn-primary"
                  onClick={() => setViewMode("translation")}
                >
                  <Languages size={14} /> Revisar Tradução
                </button>
              )}
            </>
          )}
        </div>

        <div className="inspector-card">
          <div className="inspector-card-subtitle">Etapas do Pipeline</div>
          <div className="inspector-stage-list">
            <div
              className="inspector-stage-item"
              style={{
                color: canEditLayout ? "var(--warning)" : "var(--text-muted)",
              }}
            >
              <LayoutDashboard size={15} />
              <span className="inspector-stage-name">Layout</span>
              {canEditLayout ? (
                <span className="inspector-badge-ready layout">Pronto</span>
              ) : (
                <span className="inspector-badge-missing">Ausente</span>
              )}
            </div>

            <div
              className="inspector-stage-item"
              style={{
                color: canEditOcr
                  ? "var(--brand-primary)"
                  : "var(--text-muted)",
              }}
            >
              <ScanText size={15} />
              <span className="inspector-stage-name">OCR</span>
              {canEditOcr ? (
                <span className="inspector-badge-ready ocr">Pronto</span>
              ) : (
                <span className="inspector-badge-missing">Ausente</span>
              )}
            </div>

            <div
              className="inspector-stage-item"
              style={{
                color: canEditTranslation
                  ? "var(--success)"
                  : "var(--text-muted)",
              }}
            >
              <Languages size={15} />
              <span className="inspector-stage-name">Tradução</span>
              {canEditTranslation ? (
                <span className="inspector-badge-ready translation">
                  Pronto
                </span>
              ) : (
                <span className="inspector-badge-missing">Ausente</span>
              )}
            </div>
          </div>
        </div>

        <div className="inspector-card">
          <div className="inspector-card-subtitle">Métricas e Arquivo</div>
          <div className="inspector-metrics-list">
            <div className="inspector-row">
              <span className="inspector-label-muted">Arquivo:</span>
              <span style={{ fontWeight: 600 }}>{page?.name || "Desconhecido"}</span>
            </div>
            <div className="inspector-row">
              <span className="inspector-label-muted">Resolução:</span>
              <span>
                {bgSize.width > 0
                  ? `${bgSize.width} × ${bgSize.height} px`
                  : "Carregando..."}
              </span>
            </div>
            <div className="inspector-row">
              <span className="inspector-label-muted">Status:</span>
              <span style={{ color: isPending ? "#f87171" : "#10b981", fontWeight: 600 }}>
                {isPending ? "Pendente" : "Em Progresso"}
              </span>
            </div>
            {boxes.length > 0 && (
              <>
                <div className="inspector-divider" />
                <div className="inspector-row">
                  <span className="inspector-label-muted">Diálogos de Fala:</span>
                  <span style={{ color: "#7dd3fc", fontWeight: 600 }}>{dialogueCount}</span>
                </div>
                <div className="inspector-row">
                  <span className="inspector-label-muted">Efeitos Sonoros (SFX):</span>
                  <span style={{ color: "#f59e0b", fontWeight: 600 }}>{sfxCount}</span>
                </div>
                <div className="inspector-row">
                  <span className="inspector-label-muted">Caracteres Extraídos:</span>
                  <span>{charCount > 0 ? charCount : "Aguardando OCR"}</span>
                </div>
                <div className="inspector-row">
                  <span className="inspector-label-muted">Caracteres Traduzidos:</span>
                  <span>{transCount > 0 ? transCount : "Aguardando Tradução"}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {boxes.length > 0 && (
          <div className="inspector-script-section">
            <button
              type="button"
              className="inspector-btn-script"
              onClick={() => setShowScriptPreview(!showScriptPreview)}
            >
              <FileText size={14} />
              <span>{showScriptPreview ? "Ocultar Roteiro da Página" : "Ver Roteiro da Página (.txt)"}</span>
            </button>

            {showScriptPreview && (
              <div className="inspector-script-drawer">
                <div className="inspector-script-drawer-header">
                  <span className="drawer-title">Roteiro Sequencial</span>
                  <button
                    type="button"
                    className="btn-copy-script"
                    onClick={handleCopyScript}
                    title="Copiar texto formatado para a área de transferência"
                  >
                    {isCopied ? <Check size={12} /> : <Copy size={12} />}
                    <span>{isCopied ? "Copiado!" : "Copiar"}</span>
                  </button>
                </div>
                <div className="inspector-script-content">
                  {boxes.map((b, idx) => (
                    <div key={b.id || idx} className="script-line-item">
                      <div className="script-line-num">
                        #{String(idx + 1).padStart(2, "0")} {b.is_sfx ? "[SFX]" : "[Fala]"}
                      </div>
                      <div className="script-line-text">
                        {b.text ? (
                          <div className="script-orig">{b.text}</div>
                        ) : (
                          <div className="script-empty">(Aguardando OCR)</div>
                        )}
                        {b.translated && (
                          <div className="script-trans">↳ {b.translated}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="inspector-card inspector-danger-card">
          <div className="inspector-danger-header">
            <AlertTriangle size={13} style={{ color: "#ef4444" }} />
            <span className="inspector-card-subtitle" style={{ color: "#ef4444", margin: 0 }}>
              Zona de Risco
            </span>
          </div>

          <div className="inspector-actions-stack" style={{ marginTop: "8px" }}>
            <button
              type="button"
              className="inspector-btn-danger-full"
              onClick={() => setIsRestartModalOpen(true)}
            >
              Redefinir Página (Apagar Tudo)
            </button>

            {isDevUnlocked && (
              <>
                <div className="inspector-divider" />
                <button
                  type="button"
                  className={`inspector-btn-debug ${showOcrDebug ? "active" : ""}`}
                  onClick={() => setShowOcrDebug(!showOcrDebug)}
                >
                  <Terminal size={14} />{" "}
                  {showOcrDebug
                    ? "Ocultar Painéis (Debug)"
                    : "Exibir Painéis (Debug)"}
                </button>
              </>
            )}
          </div>
        </div>

        {isPending && (
          <div className="inspector-empty-banner">
            Esta página ainda não possui dados de texto ou tradução.
          </div>
        )}
      </div>
    </div>
  );
});

export default SeamlessOverviewInspector;
