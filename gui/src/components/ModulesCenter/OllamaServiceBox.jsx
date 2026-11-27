import React, { useState } from "react";
import { Terminal, Loader2, Cpu, RefreshCw, Download, X } from "lucide-react";
import { formatDownloadTelemetry } from "../../utils/downloadFormatters";
import ConfirmModal from "../ConfirmModal";

const OllamaServiceBox = React.memo(function OllamaServiceBox({
  isOllamaRunningStatus,
  ollamaState,
  checkModules,
  isCheckingOllama,
  clearVRAM,
  startOllamaService,
  isOllamaStarting,
  ollamaInstallProgress,
  isOllamaInstalling,
  installIsolatedOllama,
  cancelIsolatedOllamaInstall,
}) {
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const isNotInstalled = ollamaState === "not_installed";
  const isConnecting = isOllamaStarting || ollamaState === "verifying" || ollamaState === "starting";
  const statusClass = isOllamaRunningStatus
    ? "online"
    : isOllamaInstalling || isConnecting
    ? "starting"
    : "offline";

  const statusLabel = isOllamaRunningStatus
    ? "127.0.0.1:11435"
    : isOllamaInstalling
    ? `${Math.round(ollamaInstallProgress?.percent || 0)}%`
    : isConnecting
    ? "Iniciando..."
    : isNotInstalled
    ? "Não Instalado"
    : "Offline";

  return (
    <div className={`pipeline-utility-box`}>
      <div className={`utility-top-info`}>
        <div className={`utility-title-row`}>
          <Terminal size={13} className={`text-muted`} />
          <div className={`utility-label`}>{`Serviço Ollama`}</div>
        </div>
        <div className={`status-pill-subtle ${statusClass}`}>
          <div className={`dot-pulse`} />
          {statusLabel}
        </div>
      </div>
      <div className={`utility-actions-deck`}>
        {isOllamaRunningStatus ? (
          <React.Fragment>
            <button
              type="button"
              className={`btn-utility-action`}
              onClick={checkModules}
              disabled={isCheckingOllama}
              title={`Reverificar status dos motores`}
            >
              <Loader2 size={11} className={isCheckingOllama ? `spin` : ``} />
              <div>{`Verificar`}</div>
            </button>
            <button
              type="button"
              className={`btn-utility-action vram`}
              onClick={clearVRAM}
              title={`Libera a memória VRAM e limpa caches do PyTorch`}
            >
              <Cpu size={11} />
              <div>{`Liberar VRAM`}</div>
            </button>
            <button
              type="button"
              className={`btn-utility-action destructive`}
              onClick={() => setIsResetModalOpen(true)}
              title={`Restauração de Fábrica (Reparo Profundo)`}
            >
              <RefreshCw
                size={11}
                style={{
                  color: `#ff4444`,
                }}
              />
              <div
                style={{
                  color: `#ff4444`,
                }}
              >{`Restaurar Ambiente`}</div>
            </button>
          </React.Fragment>
        ) : isOllamaInstalling ? (
          <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: "6px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "10.5px" }}>
              <span
                style={{
                  color: "var(--text-secondary, #a1a1aa)",
                  fontFamily: "var(--font-mono, monospace)",
                  fontVariantNumeric: "tabular-nums",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  flex: 1,
                }}
                title={ollamaInstallProgress?.message || ""}
              >
                {formatDownloadTelemetry({
                  progress: ollamaInstallProgress?.percent || 0,
                  speed_mbps: ollamaInstallProgress?.speed_mbps || 0,
                  eta_seconds: ollamaInstallProgress?.eta_seconds || 0,
                  downloaded_bytes: ollamaInstallProgress?.downloaded_bytes || 0,
                  total_bytes: ollamaInstallProgress?.total_bytes || 0,
                  text: ollamaInstallProgress?.status === "extracting" ? "Extraindo motor..." : (ollamaInstallProgress?.message || "Baixando pacote portátil..."),
                  fallbackSize: "~450 MB",
                })}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                <span
                  style={{
                    color: "var(--brand-primary, #8b5cf6)",
                    fontFamily: "var(--font-mono, monospace)",
                    fontVariantNumeric: "tabular-nums",
                    fontSize: "10px",
                    fontWeight: 600,
                  }}
                >
                  {`${Math.round(ollamaInstallProgress?.percent || 0)}%`}
                </span>
                <button
                  type="button"
                  className={`btn-icon-trash`}
                  onClick={cancelIsolatedOllamaInstall}
                  title={`Cancelar download do motor`}
                  aria-label={`Cancelar download do motor`}
                  style={{ width: "18px", height: "18px", padding: 0, display: "inline-flex", alignItems: "center", justifyContent: "center" }}
                >
                  <X size={10} />
                </button>
              </div>
            </div>
            <div
              style={{
                width: "100%",
                height: "3px",
                background: "rgba(255, 255, 255, 0.08)",
                borderRadius: "2px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  background: "var(--brand-primary, #8b5cf6)",
                  borderRadius: "2px",
                  transition: "width 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
                  width: `${Math.max(3, Math.min(100, ollamaInstallProgress?.percent || 0))}%`,
                }}
              />
            </div>
          </div>
        ) : isNotInstalled ? (
          <button
            type="button"
            className={`btn-utility-primary`}
            onClick={installIsolatedOllama}
            title={`Baixar e configurar o motor Ollama portátil de forma isolada no Visionary (~450 MB)`}
          >
            <Download size={11} />
            <div>{`Baixar Motor Ollama (~450 MB)`}</div>
          </button>
        ) : (
          <button
            type="button"
            className={`btn-utility-primary`}
            onClick={startOllamaService}
            disabled={isOllamaStarting || isConnecting}
          >
            <Loader2 size={11} className={isOllamaStarting ? `spin` : ``} />
            <div>{isOllamaStarting ? `Iniciando...` : `Iniciar Serviço`}</div>
          </button>
        )}
      </div>

      <ConfirmModal
        isOpen={isResetModalOpen}
        title="Restaurar Ambiente de IA?"
        message="CUIDADO: Isso removerá todos os modelos neurais baixados e restaurará as configurações originais do sistema. O Visionary precisará reinstalar os motores do zero na próxima execução. Deseja continuar?"
        confirmText="Restaurar de Fábrica"
        cancelText="Cancelar"
        onConfirm={() => {
          setIsResetModalOpen(false);
          if (window.electronAPI?.factoryReset) {
            window.electronAPI.factoryReset();
          }
        }}
        onClose={() => setIsResetModalOpen(false)}
      />
    </div>
  );
});

export default OllamaServiceBox;
