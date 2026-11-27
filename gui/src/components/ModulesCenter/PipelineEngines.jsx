import React, { useState } from "react";
import {
  Layers,
  Cpu,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Check,
  Trash2,
  Download,
  ScanText,
  Eye,
  X,
} from "lucide-react";
import { formatDownloadTelemetry } from "../../utils/downloadFormatters";
import ConfirmModal from "../ConfirmModal";

const PipelineEngines = React.memo(function PipelineEngines({
  children,
  installedOcrCount,
  hardwareStats,
  formatGpuDisplayName,
  isOcrInstalled,
  ollamaModelsTags,
  uninstallCoreEngine,
  installCoreEngine,
  isYoloInstalled,
  ollamaModelsInfo,
  deleteHFModel,
  downloadHFModel,
  cancelHFModel,
  isFlorenceInstalled: _isFlorenceInstalled,
  ollamaDownloads,
}) {
  const isFlorenceLargeInstalled = ollamaModelsInfo.florence2_large?.status === `installed`;
  const isFlorenceBaseInstalled = ollamaModelsInfo.florence2?.status === `installed`;
  const isAnyFlorenceInstalled = isFlorenceLargeInstalled || isFlorenceBaseInstalled;
  const [modalConfig, setModalConfig] = useState(null);

  const florenceTitle = isFlorenceBaseInstalled && !isFlorenceLargeInstalled
    ? `Florence-2 Base`
    : `Florence-2 Large`;

  const florenceSubtitle = isFlorenceBaseInstalled && !isFlorenceLargeInstalled
    ? `OCR Padrão (0.23B) · ~465 MB`
    : `OCR de Alta Precisão (0.77B) · ~1.43 GB`;

  return (
    <div className={`modules-pipeline-panel`}>
      <div className={`panel-section-header`}>
        <div className={`section-title-wrap`}>
          <Layers size={14} className={`brand-purple-icon`} />
          <div className={`section-heading`}>{`Motores do Pipeline`}</div>
        </div>
        <div className={`section-counter-badge`}>
          {installedOcrCount}
          {`/3 Prontos`}
        </div>
      </div>
      <div className={`pipeline-cards-deck`}>
        {/* PyTorch Core */}
        <div className={`pipeline-engine-card`}>
          <div className={`card-top-row`}>
            <div className={`engine-avatar core`}>
              <Cpu size={15} />
            </div>
            <div className={`card-title-block`}>
              <div className={`engine-title-text`}>{`PyTorch Core`}</div>
              <div className={`engine-sub-type`}>
                {isOcrInstalled
                  ? (hardwareStats.cuda_available
                      ? `CUDA ${hardwareStats.cuda_runtime_version || hardwareStats.cuda_version} · FP16`
                      : (hardwareStats.cuda_recommendation?.status === "cpu_only"
                          ? `Modo CPU (GPU sem aceleração)`
                          : `Modo CPU`))
                  : (hardwareStats.cuda_recommendation?.status === "driver_outdated"
                      ? `Driver Desatualizado (Requer CUDA >= 11.8)`
                      : (hardwareStats.cuda_driver_version || hardwareStats.cuda_version
                          ? `Compatível com CUDA ${hardwareStats.cuda_driver_version || hardwareStats.cuda_version}`
                          : `Modo CPU`))}
              </div>
            </div>
            <div className={`card-badge-slot`}>
              {isOcrInstalled && !ollamaModelsTags.ocr ? (
                <div className={`badge-status ready`}>
                  <CheckCircle2 size={10} />
                  {` Pronto`}
                </div>
              ) : ollamaModelsTags.ocr ? (
                <div className={`badge-status busy`}>
                  <Loader2 size={10} className={`spin`} />
                  {ollamaModelsTags.ocr.mode === "uninstall" || ollamaModelsTags.ocr.text?.includes("Desinstalando") || ollamaModelsTags.ocr.text?.includes("Removendo")
                    ? (ollamaModelsTags.ocr.progress > 0 && ollamaModelsTags.ocr.progress < 100
                        ? ` Desinstalando ${(ollamaModelsTags.ocr.progress || 0).toFixed(0)}%`
                        : ` Desinstalando`)
                    : ollamaModelsTags.ocr.progress >= 99
                    ? ` Instalando`
                    : ollamaModelsTags.ocr.progress > 0
                    ? ` ${(ollamaModelsTags.ocr.progress || 0).toFixed(0)}%`
                    : ` Instalando`}
                </div>
              ) : (
                <div className={`badge-status missing`}>
                  <Download size={10} />
                  {` Disponível`}
                </div>
              )}
            </div>
          </div>
          <div className={`engine-description-text`}>
            {`Base neural para aceleração por GPU com tensores FP16.`}
          </div>
          {hardwareStats.cuda_recommendation &&
            !ollamaModelsTags.ocr &&
            hardwareStats.cuda_recommendation.status !== "ok" &&
            hardwareStats.cuda_recommendation.status !== "no_gpu" &&
            hardwareStats.cuda_recommendation.status !== "ready_for_install" &&
            (isOcrInstalled || hardwareStats.cuda_recommendation.status === "driver_outdated") && (
              <div
                className={`pipeline-engine-warning-banner`}
                title={hardwareStats.cuda_recommendation.action || ""}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "5px 8px",
                  margin: "6px 0 4px 0",
                  borderRadius: "4px",
                  fontSize: "11px",
                  lineHeight: "1.3",
                  backgroundColor: "rgba(234, 179, 8, 0.12)",
                  border: "1px solid rgba(234, 179, 8, 0.28)",
                  color: "#eab308",
                }}
              >
                <AlertCircle size={12} style={{ flexShrink: 0 }} />
                <span>{hardwareStats.cuda_recommendation.message}</span>
              </div>
            )}
          {ollamaModelsTags.ocr ? (
            <div className={`pipeline-engine-telemetry`}>
              <div className={`pipeline-telemetry-meta`}>
                <span className={`pipeline-telemetry-text`} title={ollamaModelsTags.ocr.text || ""}>
                  {formatDownloadTelemetry({
                    progress: ollamaModelsTags.ocr.progress || 0,
                    speed_mbps: 0,
                    eta_seconds: 0,
                    downloaded_bytes: ollamaModelsTags.ocr.downloaded_bytes || 0,
                    total_bytes: ollamaModelsTags.ocr.total_bytes || 0,
                    text: ollamaModelsTags.ocr.text || (isOcrInstalled ? "Desinstalando dependências..." : "Instalando dependências..."),
                    compact: true,
                    showSpeed: false,
                    showEta: false,
                  })}
                </span>
                <span className={`pipeline-telemetry-pct`}>
                  {`${(ollamaModelsTags.ocr.progress || 0).toFixed(0)}%`}
                </span>
              </div>
              <div className={`sober-progress-track`}>
                <div
                  className={`sober-progress-fill`}
                  style={{
                    width: `${(ollamaModelsTags.ocr.progress || 0) > 0 ? Math.max(2, Math.min(100, ollamaModelsTags.ocr.progress || 0)) : 0}%`,
                  }}
                />
              </div>
            </div>
          ) : (
            <div className={`card-footer-row`}>
              <div className={`engine-chip-tag`} title={hardwareStats.gpu_name}>
                {hardwareStats.gpu_name ? formatGpuDisplayName(hardwareStats.gpu_name) : `GPU`}
              </div>
              <div className={`card-action-slot`}>
                {ollamaModelsTags.ocr ? (
                  <button
                    type="button"
                    className={`btn-engine-action secondary`}
                    disabled
                  >
                    <Loader2 size={11} className={`spin`} />
                    {ollamaModelsTags.ocr.text?.includes("Desinstalando")
                      ? ` Desinstalando...`
                      : ` Instalando...`}
                  </button>
                ) : isOcrInstalled ? (
                  <div className={`engine-installed-row`}>
                    <div className={`engine-ready-indicator`}>
                      <Check size={12} />
                      {` Ativo`}
                    </div>
                    <button
                      type="button"
                      className={`btn-icon-trash`}
                      onClick={() => setModalConfig({
                        title: 'Desinstalar PyTorch Core?',
                        message: 'Isso removerá o ambiente virtual PyTorch e as dependências de aceleração GPU (CUDA/DirectML). O Visionary precisará reinstalar o motor para executar Layout e OCR.',
                        confirmText: 'Desinstalar Motor',
                        action: uninstallCoreEngine,
                      })}
                      title={`Desinstalar PyTorch e pacotes GPU`}
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={`btn-engine-action primary`}
                    onClick={installCoreEngine}
                  >
                    <Download size={11} />
                    {` Instalar`}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Comic-YOLO */}
        <div className={`pipeline-engine-card`}>
          <div className={`card-top-row`}>
            <div className={`engine-avatar yolo`}>
              <ScanText size={15} />
            </div>
            <div className={`card-title-block`}>
              <div className={`engine-title-text`}>{`Comic-YOLO`}</div>
              <div className={`engine-sub-type`}>{`Detector de Balões · ~59 MB`}</div>
            </div>
            <div className={`card-badge-slot`}>
              {ollamaModelsInfo.yolo_detector?.status === `deleting` ? (
                <div className={`badge-status busy`}>
                  <Loader2 size={10} className={`spin`} />
                  {` Removendo`}
                </div>
              ) : isYoloInstalled ? (
                <div className={`badge-status ready`}>
                  <CheckCircle2 size={10} />
                  {` Pronto`}
                </div>
              ) : ollamaModelsInfo.yolo_detector?.status === `downloading` ? (
                <div className={`badge-status busy`}>
                  <Loader2 size={10} className={`spin`} />
                  {ollamaModelsInfo.yolo_detector?.progress >= 99
                    ? ` Instalando`
                    : ` ${(ollamaModelsInfo.yolo_detector.progress || 0).toFixed(0)}%`}
                </div>
              ) : (
                <div className={`badge-status missing`}>
                  <Download size={10} />
                  {` Disponível`}
                </div>
              )}
            </div>
          </div>
          <div className={`engine-description-text`}>
            {`Detecção neural de balões de fala e ordenação RTL (da direita para a esquerda).`}
          </div>
          {ollamaModelsInfo.yolo_detector?.status === `downloading` ? (
            <div className={`pipeline-engine-telemetry`}>
              <div className={`pipeline-telemetry-meta`}>
                <span className={`pipeline-telemetry-text`} title={ollamaModelsInfo.yolo_detector.message || ""}>
                  {formatDownloadTelemetry({
                    progress: ollamaModelsInfo.yolo_detector.progress || 0,
                    speed_mbps: 0,
                    eta_seconds: 0,
                    downloaded_bytes: ollamaModelsInfo.yolo_detector.downloaded_bytes || 0,
                    total_bytes: ollamaModelsInfo.yolo_detector.total_bytes || 0,
                    fallbackSize: "~59 MB",
                    text: ollamaModelsInfo.yolo_detector.message || "",
                    compact: true,
                    showSpeed: false,
                    showEta: false,
                  })}
                </span>
                <div className={`pipeline-telemetry-actions`}>
                  <span className={`pipeline-telemetry-pct`}>
                    {ollamaModelsInfo.yolo_detector?.progress >= 99
                      ? `99%`
                      : `${(ollamaModelsInfo.yolo_detector.progress || 0).toFixed(0)}%`}
                  </span>
                  {cancelHFModel && (
                    <button
                      type="button"
                      className={`btn-icon-cancel-dl`}
                      onClick={() => cancelHFModel(`yolo_detector`, `Comic-YOLO`)}
                      title={`Cancelar download`}
                    >
                      <X size={11} />
                    </button>
                  )}
                </div>
              </div>
              <div className={`sober-progress-track`}>
                <div
                  className={`sober-progress-fill`}
                  style={{
                    width: `${(ollamaModelsInfo.yolo_detector.progress || 0) > 0 ? Math.max(2, Math.min(100, ollamaModelsInfo.yolo_detector.progress || 0)) : 0}%`,
                  }}
                />
              </div>
            </div>
          ) : (
            <div className={`card-footer-row`}>
              <div className={`engine-chip-tag`}>{`YOLOv8 Manga`}</div>
              <div className={`card-action-slot`}>
                {ollamaModelsInfo.yolo_detector?.status === `deleting` ? (
                  <button
                    type="button"
                    className={`btn-engine-action secondary`}
                    disabled
                  >
                    <Loader2 size={11} className={`spin`} />
                    {` Removendo...`}
                  </button>
                ) : isYoloInstalled ? (
                  <div className={`engine-installed-row`}>
                    <div className={`engine-ready-indicator`}>
                      <Check size={12} />
                      {` Em Disco`}
                    </div>
                    <button
                      type="button"
                      className={`btn-icon-trash`}
                      onClick={() => setModalConfig({
                        title: 'Remover Comic-YOLO?',
                        message: 'Deseja apagar os pesos neurais do detector Comic-YOLO (~59 MB)? O modelo precisará ser baixado novamente para detecção de balões.',
                        confirmText: 'Excluir Modelo',
                        action: () => deleteHFModel(`yolo_detector`, `YOLO Detector`),
                      })}
                      title={`Remover do disco`}
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={`btn-engine-action secondary`}
                    onClick={() => downloadHFModel(`yolo_detector`, `YOLO Detector`)}
                    disabled={!isOcrInstalled || ollamaDownloads.yolo_detector}
                  >
                    <Download size={11} />
                    {` Baixar`}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Florence-2 Vision */}
        <div className={`pipeline-engine-card`}>
          <div className={`card-top-row`}>
            <div className={`engine-avatar florence`}>
              <Eye size={15} />
            </div>
            <div className={`card-title-block`}>
              <div className={`engine-title-text`}>{florenceTitle}</div>
              <div className={`engine-sub-type`}>{florenceSubtitle}</div>
            </div>
            <div className={`card-badge-slot`}>
              {(ollamaModelsInfo.florence2_large?.status === `deleting` || ollamaModelsInfo.florence2?.status === `deleting`) ? (
                <div className={`badge-status busy`}>
                  <Loader2 size={10} className={`spin`} />
                  {` Removendo`}
                </div>
              ) : isAnyFlorenceInstalled ? (
                <div className={`badge-status ready`}>
                  <CheckCircle2 size={10} />
                  {` Pronto`}
                </div>
              ) : (ollamaModelsInfo.florence2_large?.status === `downloading` || ollamaModelsInfo.florence2?.status === `downloading`) ? (
                <div className={`badge-status busy`}>
                  <Loader2 size={10} className={`spin`} />
                  {(() => {
                    const p = ollamaModelsInfo.florence2_large?.progress || ollamaModelsInfo.florence2?.progress || 0;
                    return p >= 99 ? ` Instalando` : ` ${p.toFixed(0)}%`;
                  })()}
                </div>
              ) : (
                <div className={`badge-status missing`}>
                  <Download size={10} />
                  {` Disponível`}
                </div>
              )}
            </div>
          </div>
          <div className={`engine-description-text`}>
            {`Visão neural de alta fidelidade para fontes estilizadas, balões inclinados e onomatopeias em inglês.`}
          </div>
          {(ollamaModelsInfo.florence2_large?.status === `downloading` || ollamaModelsInfo.florence2?.status === `downloading`) ? (
            <div className={`pipeline-engine-telemetry`}>
              {(() => {
                const isLargeDownloading = ollamaModelsInfo.florence2_large?.status === `downloading`;
                const activeFlorenceId = isLargeDownloading ? `florence2_large` : `florence2`;
                const info = isLargeDownloading
                  ? ollamaModelsInfo.florence2_large
                  : ollamaModelsInfo.florence2;
                return (
                  <>
                    <div className={`pipeline-telemetry-meta`}>
                      <span className={`pipeline-telemetry-text`} title={info?.message || ""}>
                        {formatDownloadTelemetry({
                          progress: info?.progress || 0,
                          speed_mbps: 0,
                          eta_seconds: 0,
                          downloaded_bytes: info?.downloaded_bytes || 0,
                          total_bytes: info?.total_bytes || 0,
                          fallbackSize: "~1.43 GB",
                          text: info?.message || "",
                          compact: true,
                          showSpeed: false,
                          showEta: false,
                        })}
                      </span>
                      <div className={`pipeline-telemetry-actions`}>
                        <span className={`pipeline-telemetry-pct`}>
                          {(info?.progress || 0) >= 99
                            ? `99%`
                            : `${(info?.progress || 0).toFixed(0)}%`}
                        </span>
                        {cancelHFModel && (
                          <button
                            type="button"
                            className={`btn-icon-cancel-dl`}
                            onClick={() => cancelHFModel(activeFlorenceId, florenceTitle)}
                            title={`Cancelar download`}
                          >
                            <X size={11} />
                          </button>
                        )}
                      </div>
                    </div>
                    <div className={`sober-progress-track`}>
                      <div
                        className={`sober-progress-fill`}
                        style={{
                          width: `${(info?.progress || 0) > 0 ? Math.max(2, Math.min(100, info?.progress || 0)) : 0}%`,
                        }}
                      />
                    </div>
                  </>
                );
              })()}
            </div>
          ) : (
            <div className={`card-footer-row`}>
              <div className={`engine-chip-tag`}>{`Safetensors FP16`}</div>
              <div className={`card-action-slot`}>
                {(ollamaModelsInfo.florence2_large?.status === `deleting` || ollamaModelsInfo.florence2?.status === `deleting`) ? (
                  <button
                    type="button"
                    className={`btn-engine-action secondary`}
                    disabled
                  >
                    <Loader2 size={11} className={`spin`} />
                    {` Removendo...`}
                  </button>
                ) : isAnyFlorenceInstalled ? (
                  <div className={`engine-installed-row`}>
                    <div className={`engine-ready-indicator`}>
                      <Check size={12} />
                      {` Em Disco`}
                    </div>
                    <button
                      type="button"
                      className={`btn-icon-trash`}
                      onClick={() => setModalConfig({
                        title: `Remover ${florenceTitle}?`,
                        message: `Deseja apagar os pesos neurais do modelo de visão ${florenceTitle}? O Visionary precisará baixá-lo novamente para extração de texto OCR.`,
                        confirmText: 'Excluir Modelo',
                        action: () => deleteHFModel(isFlorenceLargeInstalled ? `florence2_large` : `florence2`, isFlorenceLargeInstalled ? `Florence-2 Large` : `Florence-2 Base`),
                      })}
                      title={`Remover do disco`}
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={`btn-engine-action secondary`}
                    onClick={() => downloadHFModel(`florence2_large`, `Florence-2 Large`)}
                    disabled={!isOcrInstalled || ollamaDownloads.florence2_large || ollamaDownloads.florence2}
                  >
                    <Download size={11} />
                    {` Baixar`}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
      {children}

      <ConfirmModal
        isOpen={Boolean(modalConfig)}
        title={modalConfig?.title || "Confirmar Exclusão?"}
        message={modalConfig?.message || "Esta ação removerá o arquivo selecionado."}
        confirmText={modalConfig?.confirmText || "Excluir"}
        cancelText="Cancelar"
        onConfirm={() => {
          if (modalConfig?.action) {
            modalConfig.action();
          }
          setModalConfig(null);
        }}
        onClose={() => setModalConfig(null)}
      />
    </div>
  );
});

export default PipelineEngines;
