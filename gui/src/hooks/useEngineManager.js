import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "../contexts/ToastContext";
import { useWorkspaceStore } from "../stores/useWorkspaceStore";
import { clientApi } from "../api/bridge";
import { safeSetStorageItem } from "../utils/storage";
import { useHardwareTelemetry } from "./useHardwareTelemetry";
import { useOllamaManager } from "./useOllamaManager";
import { useHFEngineManager } from "./useHFEngineManager";
import { useCoreEngineInstaller } from "./useCoreEngineInstaller";
import { useEngineEventSync } from "./useEngineEventSync";

/**
 * Hook Agregador de Gestão de Motores e IA do Visionary Studio.
 * Orquestra hooks especializados preservando 100% da interface e contratos legados.
 */
export function useEngineManager(isActive = true) {
  const { addToast } = useToast();

  const [moduleStatus, setModuleStatus] = useState(() => {
    try {
      const cached = localStorage.getItem("visionary:cached_module_status");
      const parsed = cached ? JSON.parse(cached) : null;
      return {
        ocr: parsed?.ocr || { state: "verifying", progress: 0 },
        cuda: parsed?.cuda || { state: "verifying", progress: 0 },
        ollama: { state: "verifying", progress: 0 },
      };
    } catch {
      return {
        ocr: { state: "verifying", progress: 0 },
        cuda: { state: "verifying", progress: 0 },
        ollama: { state: "verifying", progress: 0 },
      };
    }
  });

  const [storageStats, setStorageStats] = useState(() => {
    try {
      const cached = localStorage.getItem("visionary:cached_storage_stats");
      return cached ? JSON.parse(cached) : null;
    } catch {
      return null;
    }
  });

  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const [userSettings, setUserSettings] = useState({ transPol: "" });
  const [hasLoadedInitialSettings, setHasLoadedInitialSettings] = useState(false);
  const previousSavedTransPolRef = useRef(null);

  // ── Sub-hooks Especializados ──
  const {
    hardwareStats,
    setHardwareStats,
    applyHardwareStats,
    fetchHardwareTelemetry,
  } = useHardwareTelemetry();

  // Forward declaration para checkModules
  const checkModulesRef = useRef(null);
  const checkModulesProxy = useCallback((silent = false, includeSlow = true) => {
    if (checkModulesRef.current) {
      return checkModulesRef.current(silent, includeSlow);
    }
  }, []);

  const {
    ollamaModels,
    setOllamaModels,
    ollamaModelsInfo,
    setOllamaModelsInfo,
    ollamaModelsTags,
    setOllamaModelsTags,
    ollamaModelsDetails,
    setOllamaModelsDetails,
    ollamaDownloads,
    setOllamaDownloads,
    isCheckingOllama,
    setIsCheckingOllama,
    isOllamaStarting,
    startOllamaService,
    pullOllamaModel: basePullOllamaModel,
    deleteOllamaModel,
    cancelOllamaDownload,
    ollamaInstallProgress,
    isOllamaInstalling,
    installIsolatedOllama,
    cancelIsolatedOllamaInstall,
    setOllamaInstallProgress,
  } = useOllamaManager({
    addToast,
    setModuleStatus,
    checkModules: checkModulesProxy,
  });

  const ollamaModelsTagsRef = useRef(ollamaModelsTags);
  useEffect(() => { ollamaModelsTagsRef.current = ollamaModelsTags; }, [ollamaModelsTags]);

  const coreStateEpochRef = useRef(0);
  const lastCoreCompletionRef = useRef({ state: null, timestamp: 0 });
  const hfStateGuardRef = useRef({});

  const handleHFStateChange = useCallback((modelIds, targetState) => {
    coreStateEpochRef.current += 1;
    const now = Date.now();
    for (const id of modelIds || []) {
      if (!targetState) {
        delete hfStateGuardRef.current[id];
      } else {
        hfStateGuardRef.current[id] = { state: targetState, timestamp: now };
      }
    }
  }, []);

  const { downloadHFModel, deleteHFModel, cancelHFModel } = useHFEngineManager({
    addToast,
    checkModules: checkModulesProxy,
    setIsCheckingOllama,
    setOllamaDownloads,
    setOllamaModelsInfo,
    onHFStateChange: handleHFStateChange,
  });

  const handleCoreStateChange = useCallback((targetState) => {
    coreStateEpochRef.current += 1;
    if (targetState === "installed" || targetState === "not_installed") {
      lastCoreCompletionRef.current = { state: targetState, timestamp: Date.now() };
    } else if (targetState === "installing" || targetState === "uninstalling") {
      lastCoreCompletionRef.current = { state: null, timestamp: 0 };
    }
  }, []);

  const {
    installCoreEngine,
    uninstallCoreEngine,
    clearVRAM,
    handleCoreEngineProgress,
  } = useCoreEngineInstaller({
    setOllamaModelsTags,
    setModuleStatus,
    checkModules: checkModulesProxy,
    addToast,
    setHardwareStats,
    onCoreStateChange: handleCoreStateChange,
  });

  const handleCoreEngineProgressRef = useRef(handleCoreEngineProgress);
  useEffect(() => { handleCoreEngineProgressRef.current = handleCoreEngineProgress; }, [handleCoreEngineProgress]);

  const addToastRef = useRef(addToast);
  useEffect(() => { addToastRef.current = addToast; }, [addToast]);

  const setOllamaInstallProgressRef = useRef(setOllamaInstallProgress);
  useEffect(() => { setOllamaInstallProgressRef.current = setOllamaInstallProgress; }, [setOllamaInstallProgress]);

  // ── Sincronização e Checagem de Módulos ──
  const moduleStatusRef = useRef(moduleStatus);
  useEffect(() => { moduleStatusRef.current = moduleStatus; }, [moduleStatus]);

  const ollamaModelsCountRef = useRef(ollamaModels.length);
  useEffect(() => { ollamaModelsCountRef.current = ollamaModels.length; }, [ollamaModels.length]);

  const inFlightPromiseRef = useRef(null);
  const inFlightEpochRef = useRef(0);
  const inFlightIncludeSlowRef = useRef(false);

  const checkModules = useCallback(async (silent = false, includeSlow = true) => {
    if (
      inFlightPromiseRef.current &&
      inFlightEpochRef.current === coreStateEpochRef.current &&
      (!includeSlow || inFlightIncludeSlowRef.current)
    ) {
      if (!silent) setIsCheckingOllama(true);
      return inFlightPromiseRef.current;
    }

    if (!silent) setIsCheckingOllama(true);

    const checkEpochAtStart = coreStateEpochRef.current;
    const wasOcrBusyAtStart = Boolean(ollamaModelsTagsRef.current?.ocr);
    inFlightEpochRef.current = checkEpochAtStart;
    inFlightIncludeSlowRef.current = Boolean(includeSlow);

    const executeCheck = async () => {
      try {
        const slowCalls = includeSlow
          ? [
              clientApi.getModelsStatus().catch(() => null),
              clientApi.getStorageStats().catch(() => null),
            ]
          : [];
        const [modStatus, hwStats, modInfo, storStats] = await Promise.all([
          clientApi.checkModulesStatus().catch(() => null),
          clientApi.getHardwareStats().catch(() => null),
          ...slowCalls,
        ]);
        if (modStatus) {
          const isOcrBusyNow = Boolean(ollamaModelsTagsRef.current?.ocr);
          const epochChanged = coreStateEpochRef.current !== checkEpochAtStart;
          const recentTarget =
            Date.now() - lastCoreCompletionRef.current.timestamp < 3000
              ? lastCoreCompletionRef.current.state
              : null;
          const isStaleCoreResponse = Boolean(
            recentTarget && modStatus.ocr?.state && modStatus.ocr.state !== recentTarget
          );
          const protectOcrState =
            wasOcrBusyAtStart || isOcrBusyNow || epochChanged || isStaleCoreResponse;

          const nextStatus = {
            ocr: protectOcrState
              ? (moduleStatusRef.current?.ocr || { state: recentTarget || "not_installed" })
              : (modStatus.ocr || { state: "not_installed" }),
            cuda: protectOcrState
              ? (moduleStatusRef.current?.cuda || { state: recentTarget || "not_installed" })
              : (modStatus.cuda || { state: "not_installed" }),
            ollama: modStatus.ollama || { state: "not_installed" },
          };
          setModuleStatus(nextStatus);
          if (modStatus.ocr?.state === "installed" && !protectOcrState) {
            setOllamaModelsTags((prev) => {
              if (!prev.ocr) return prev;
              const isBusy =
                Boolean(prev.ocr.mode) ||
                prev.ocr.text?.includes("Desinstalando") ||
                prev.ocr.text?.includes("Removendo") ||
                prev.ocr.text?.includes("Instalando") ||
                prev.ocr.text?.includes("Baixando") ||
                (typeof prev.ocr.progress === "number" &&
                  prev.ocr.progress > 0 &&
                  prev.ocr.progress < 100);
              if (isBusy) return prev;
              const next = { ...prev };
              delete next.ocr;
              return next;
            });
          }
          if (Array.isArray(modStatus.ollamaModels)) {
            if (modStatus.ollamaModels.length > 0) {
              setOllamaModels(modStatus.ollamaModels);
              safeSetStorageItem("visionary:cached_ollama_models", JSON.stringify(modStatus.ollamaModels));
            } else if (nextStatus.ollama?.state === "installed_and_running") {
              setOllamaModels([]);
              safeSetStorageItem("visionary:cached_ollama_models", JSON.stringify([]));
            }
          }
          setUserSettings((prev) => {
            const models = modStatus.ollamaModels || [];
            if (models.length === 0) {
              return prev.transPol ? { ...prev, transPol: "" } : prev;
            }
            if (!prev.transPol) {
              return { ...prev, transPol: models[0] };
            }
            const isCurrentValid = models.some(
              (m) => m === prev.transPol || m.split(":")[0] === prev.transPol.split(":")[0]
            );
            if (!isCurrentValid) {
              return { ...prev, transPol: models[0] };
            }
            return prev;
          });
          if (modStatus.ollamaDownloads) {
            setOllamaModelsTags((prev) => ({
              ...prev,
              ...modStatus.ollamaDownloads,
            }));
          }
          if (modStatus.ollamaModelsDetails) {
            setOllamaModelsDetails(modStatus.ollamaModelsDetails);
            safeSetStorageItem("visionary:cached_ollama_models_details", JSON.stringify(modStatus.ollamaModelsDetails));
          }
          safeSetStorageItem("visionary:cached_module_status", JSON.stringify({
            ocr: nextStatus.ocr,
            cuda: nextStatus.cuda,
            ollama: { state: "verifying" },
          }));
        }
        if (includeSlow && modInfo && !modInfo.error) {
          setOllamaModelsInfo((prev) => {
            const next = { ...prev };
            const now = Date.now();
            for (const k of Object.keys(modInfo)) {
              const incoming = modInfo[k] || {};
              const existing = prev[k];
              const guard = hfStateGuardRef.current[k];

              if (existing?.status === "deleting" || guard?.state === "deleting") {
                continue;
              }
              if (
                guard &&
                (guard.state === "installed" || guard.state === "missing") &&
                now - guard.timestamp < 3000 &&
                incoming.status &&
                incoming.status !== guard.state
              ) {
                continue;
              }
              if (
                existing?.status === "downloading" &&
                incoming.status === "missing" &&
                guard?.state === "downloading" &&
                now - guard.timestamp < 4000
              ) {
                continue;
              }
              if (existing?.status === "downloading" && incoming.status === "downloading") {
                const clampedProg =
                  typeof incoming.progress === "number" && typeof existing.progress === "number"
                    ? Math.max(existing.progress, incoming.progress)
                    : (incoming.progress ?? existing.progress);
                next[k] = {
                  ...existing,
                  ...incoming,
                  ...(clampedProg !== undefined ? { progress: clampedProg } : {}),
                };
                continue;
              }
              next[k] = incoming;
            }
            safeSetStorageItem("visionary:cached_ollama_info", JSON.stringify(next));
            return next;
          });
        }
        if (hwStats) {
          const isOcrBusyNow = Boolean(ollamaModelsTagsRef.current?.ocr);
          const recentTarget =
            Date.now() - lastCoreCompletionRef.current.timestamp < 3000
              ? lastCoreCompletionRef.current.state
              : null;
          if (
            (isOcrBusyNow || recentTarget === "installed") &&
            hwStats.cuda_recommendation?.status === "cpu_only"
          ) {
            applyHardwareStats({
              ...hwStats,
              cuda_recommendation: {
                ...hwStats.cuda_recommendation,
                status: "ok",
                message: "",
              },
            });
          } else {
            applyHardwareStats(hwStats);
          }
        }
        if (includeSlow && storStats && storStats.success) {
          setStorageStats(storStats);
          safeSetStorageItem("visionary:cached_storage_stats", JSON.stringify(storStats));
        }
      } catch (e) {
        console.error(e);
      } finally {
        setIsCheckingOllama(false);
        setInitialLoadDone(true);
        if (inFlightEpochRef.current === checkEpochAtStart) {
          inFlightPromiseRef.current = null;
        }
      }
    };

    inFlightPromiseRef.current = executeCheck();
    return inFlightPromiseRef.current;
  }, [applyHardwareStats, setIsCheckingOllama, setOllamaModels, setOllamaModelsDetails, setOllamaModelsInfo, setOllamaModelsTags]);

  checkModulesRef.current = checkModules;

  // Pré-aquecimento imediato em background logo após o mount (não-bloqueante)
  useEffect(() => {
    checkModules(true, true);
  }, [checkModules]);

  // Carregamento inicial de configurações de modelo
  useEffect(() => {
    if (!isActive) return;
    if (hasLoadedInitialSettings) return;

    clientApi.getSettings().then((res) => {
      if (res?.selected_models?.transPol) {
        setUserSettings(res.selected_models);
        previousSavedTransPolRef.current = res.selected_models.transPol;
      } else {
        previousSavedTransPolRef.current = "";
      }
      setHasLoadedInitialSettings(true);
    }).catch(() => {
      previousSavedTransPolRef.current = "";
      setHasLoadedInitialSettings(true);
    });
  }, [isActive, hasLoadedInitialSettings]);

  // Persistência reativa de alterações no selected_models
  useEffect(() => {
    if (!hasLoadedInitialSettings) return;
    if (previousSavedTransPolRef.current === userSettings.transPol) return;
    if (!userSettings.transPol) return;

    previousSavedTransPolRef.current = userSettings.transPol;
    const settingsToSave = {
      transPol: userSettings.transPol,
      corr: userSettings.transPol,
      trans: userSettings.transPol,
    };
    clientApi.saveSettings({
      selected_models: settingsToSave,
    }).catch(() => {});
  }, [userSettings.transPol, hasLoadedInitialSettings]);

  // Polling e Inscrição no EventBus
  useEngineEventSync({
    isActive,
    checkModules,
    fetchHardwareTelemetry,
    handleHFStateChange,
    setOllamaModelsTags,
    setOllamaModelsInfo,
    moduleStatusRef,
    ollamaModelsCountRef,
    hfStateGuardRef,
    coreStateEpochRef,
    handleCoreEngineProgressRef,
    setOllamaInstallProgressRef,
    addToastRef,
  });

  const ollamaRevision = useWorkspaceStore((s) => s.ollamaRevision);

  useEffect(() => {
    if (ollamaRevision > 0 && isActive) {
      checkModules();
    }
  }, [ollamaRevision, isActive, checkModules]);

  const pullOllamaModel = useCallback((modelName) => {
    return basePullOllamaModel(modelName, moduleStatus.ollama?.state);
  }, [basePullOllamaModel, moduleStatus.ollama?.state]);

  return {
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
    setOllamaInstallProgress,
    pullOllamaModel,
    deleteOllamaModel,
    installCoreEngine,
    uninstallCoreEngine,
    clearVRAM,
    fetchHardwareTelemetry,
  };
}
