import React from "react";
import "./ModulesCenter.css";
import { Loader2, Sparkles } from "lucide-react";
import { useEngineManager } from "../hooks/useEngineManager";
import TelemetryDashboard from "./ModulesCenter/TelemetryDashboard";
import PipelineEngines from "./ModulesCenter/PipelineEngines";
import OllamaServiceBox from "./ModulesCenter/OllamaServiceBox";
import TranslationModelsGrid from "./ModulesCenter/TranslationModelsGrid";

const formatGpuDisplayName = (rawName) => {
  if (
    !rawName ||
    rawName === "Identificando..." ||
    rawName === "GPU" ||
    rawName.includes("Nenhum") ||
    rawName.includes("CPU")
  ) {
    return rawName || "GPU";
  }
  return (
    rawName
      .replace(/^(NVIDIA\s+GeForce|NVIDIA|GeForce|AMD\s+Radeon)\s+/i, "")
      .trim() || rawName
  );
};

const formatCpuDisplayName = (rawName) => {
  if (!rawName || rawName.includes("Processador")) return "Processador";
  return (
    rawName
      .replace(/\(R\)|\(TM\)/gi, "")
      .replace(/\b\d+th\s+Gen\s+/gi, "")
      .replace(/Intel\s+Core\s+/gi, "Core ")
      .replace(/AMD\s+Ryzen\s+/gi, "Ryzen ")
      .replace(/\s+/g, " ")
      .trim() || rawName
  );
};

export default function ModulesCenter({ isActive = true }) {
  const {
    moduleStatus,
    hardwareStats,
    storageStats,
    ollamaModels,
    ollamaModelsDetails,
    ollamaModelsInfo,
    ollamaModelsTags,
    ollamaDownloads,
    isCheckingOllama,
    initialLoadDone,
    isOllamaStarting,
    userSettings,
    setUserSettings,
    checkModules,
    startOllamaService,
    downloadHFModel,
    deleteHFModel,
    cancelHFModel,
    cancelOllamaDownload,
    ollamaInstallProgress,
    isOllamaInstalling,
    installIsolatedOllama,
    cancelIsolatedOllamaInstall,
    pullOllamaModel,
    deleteOllamaModel,
    installCoreEngine,
    uninstallCoreEngine,
    clearVRAM
  } = useEngineManager(isActive);

  const isOllamaRunningStatus = moduleStatus.ollama.state === `installed_and_running`;
  const isYoloInstalled = ollamaModelsInfo.yolo_detector?.status === `installed`;
  const isFlorenceLargeInstalled = ollamaModelsInfo.florence2_large?.status === `installed`;
  const isFlorenceBaseInstalled = ollamaModelsInfo.florence2?.status === `installed`;
  const isFlorenceInstalled = isFlorenceLargeInstalled || isFlorenceBaseInstalled;
  const isOcrInstalled = moduleStatus.ocr.state === `installed`;
  const installedOcrCount = +!!isOcrInstalled + +!!isYoloInstalled + +!!isFlorenceInstalled;

  const hasCachedData = Boolean(
    storageStats || (hardwareStats && hardwareStats.gpu_name !== "Identificando...")
  );

  if (!initialLoadDone && !hasCachedData) {
    return (
      <div className={`modules-hub-container`}>
        <div className={`modules-loading-splash`}>
          <Loader2 size={24} className={`spin`} style={{ color: "var(--brand-primary, #a855f7)" }} />
          <div className={`loading-splash-text`}>
            {`Identificando hardware e motores neurais...`}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`modules-hub-container`}>
      <div className={`modules-topbar`}>
        <div className={`modules-topbar-title-cluster`}>
          <div className={`topbar-icon-box`}>
            <Sparkles size={14} className={`brand-purple-icon`} />
          </div>
          <div className={`topbar-titles`}>
            <div className={`topbar-heading`}>{`Central de Módulos & IA`}</div>
            <div className={`topbar-caption`}>
              {`Motores neurais locais, visão computacional e tradução`}
            </div>
          </div>
        </div>
        <div className={`modules-telemetry-strip`}>
          <button
            type="button"
            className={`btn-sync-hardware`}
            onClick={checkModules}
            disabled={isCheckingOllama}
            title={`Recarregar status dos modelos e hardware`}
          >
            <Loader2 size={12} className={isCheckingOllama ? `spin` : ``} />
            <div>{isCheckingOllama ? `Verificando...` : `Sincronizar`}</div>
          </button>
        </div>
      </div>
      
      <div className={`modules-layout-split`}>
        {/* Left Panel */}
        <PipelineEngines
          installedOcrCount={installedOcrCount}
          hardwareStats={hardwareStats}
          formatGpuDisplayName={formatGpuDisplayName}
          isOcrInstalled={isOcrInstalled}
          ollamaModelsTags={ollamaModelsTags}
          uninstallCoreEngine={uninstallCoreEngine}
          installCoreEngine={installCoreEngine}
          isYoloInstalled={isYoloInstalled}
          ollamaModelsInfo={ollamaModelsInfo}
          deleteHFModel={deleteHFModel}
          downloadHFModel={downloadHFModel}
          cancelHFModel={cancelHFModel}
          isFlorenceInstalled={isFlorenceInstalled}
          ollamaDownloads={ollamaDownloads}
        >
          <OllamaServiceBox
            isOllamaRunningStatus={isOllamaRunningStatus}
            ollamaState={moduleStatus.ollama?.state}
            checkModules={checkModules}
            isCheckingOllama={isCheckingOllama}
            clearVRAM={clearVRAM}
            startOllamaService={startOllamaService}
            isOllamaStarting={isOllamaStarting}
            ollamaInstallProgress={ollamaInstallProgress}
            isOllamaInstalling={isOllamaInstalling}
            installIsolatedOllama={installIsolatedOllama}
            cancelIsolatedOllamaInstall={cancelIsolatedOllamaInstall}
          />
        </PipelineEngines>

        {/* Right Panel */}
        <TranslationModelsGrid
          ollamaModels={ollamaModels}
          ollamaModelsDetails={ollamaModelsDetails}
          ollamaModelsTags={ollamaModelsTags}
          ollamaDownloads={ollamaDownloads}
          userSettings={userSettings}
          setUserSettings={setUserSettings}
          hardwareStats={hardwareStats}
          pullOllamaModel={pullOllamaModel}
          deleteOllamaModel={deleteOllamaModel}
          cancelOllamaDownload={cancelOllamaDownload}
        >
          <TelemetryDashboard
            hardwareStats={hardwareStats}
            storageStats={storageStats}
            ollamaModelsCount={ollamaModels.length}
            formatGpuDisplayName={formatGpuDisplayName}
            formatCpuDisplayName={formatCpuDisplayName}
          />
        </TranslationModelsGrid>
      </div>
    </div>
  );
}
