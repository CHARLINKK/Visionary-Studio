import { useEffect } from "react";
import { clientApi, eventBus } from "../api/bridge";

/**
 * Sub-hook responsável pela sincronização em tempo real (EventBus + Polling de fallback)
 * de progresso de downloads (Ollama, Hugging Face, Core Engine) e telemetria de hardware.
 */
export function useEngineEventSync({
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
}) {
  useEffect(() => {
    if (!isActive) return;

    checkModules(false, true);

    // Polling de telemetria de hardware (VRAM, GPU, RAM do sistema):
    // Pausado automaticamente quando a janela está em segundo plano (document.hidden) para economizar ciclos de CPU
    const hwInterval = setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      fetchHardwareTelemetry();
    }, 1000);

    // Retomada instantânea ao focar na janela novamente
    const handleVisibilityChange = () => {
      if (typeof document !== "undefined" && !document.hidden && isActive) {
        fetchHardwareTelemetry();
      }
    };
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", handleVisibilityChange);
    }

    // Polling adaptativo de status de módulos:
    // Enquanto o Ollama estiver inicializando, consulta a cada 1.2s para atualização rápida.
    // Assim que tudo estiver instalado e estável, relaxa o intervalo para 5s reduzindo carga no backend.
    let lastCheckTime = Date.now();
    const statusInterval = setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      const now = Date.now();
      const isPending =
        !moduleStatusRef.current ||
        moduleStatusRef.current.ollama?.state !== "installed_and_running" ||
        ollamaModelsCountRef.current === 0;
      const threshold = isPending ? 1200 : 5000;
      if (now - lastCheckTime >= threshold) {
        lastCheckTime = now;
        checkModules(true, false);
      }
    }, 400);

    const applyDownloadsProgress = (res) => {
      if (!res || !res.success) return;
      let hasOllama = Object.keys(res.ollama || {}).length > 0;
      let hasHf = Object.keys(res.hf || {}).length > 0;

      let newlyCompletedOllama = false;
      setOllamaModelsTags((prev) => {
        if (!Object.keys(prev).some((k) => k !== "ocr" && k !== "cuda") && !hasOllama) return prev;
        let nextTags = { ...prev };
        for (let k of Object.keys(res.ollama || {})) {
          const item = res.ollama[k];
          const isDone =
            item?.status === "installed" ||
            item?.status === "completed" ||
            item?.status === "success" ||
            (typeof item?.progress === "number" && item.progress >= 100);
          if (isDone) {
            if (
              prev[k] &&
              prev[k].status !== "installed" &&
              prev[k].status !== "completed" &&
              prev[k].status !== "success"
            ) {
              newlyCompletedOllama = true;
            }
            delete nextTags[k];
          } else {
            const prevPct = typeof nextTags[k]?.progress === "number" ? nextTags[k].progress : 0;
            const nextPct = typeof item?.progress === "number" ? Math.max(prevPct, item.progress) : prevPct;
            nextTags[k] = { ...nextTags[k], ...item, progress: nextPct };
          }
        }
        for (let k of Object.keys(prev)) {
          if (k !== "ocr" && k !== "cuda" && !(res.ollama || {})[k]) {
            delete nextTags[k];
          }
        }
        return nextTags;
      });
      if (newlyCompletedOllama) {
        checkModules(true, true);
      }

      if (hasHf) {
        let newlyCompletedHf = false;
        setOllamaModelsInfo((prev) => {
          let nextInfo = { ...prev };
          for (let k of Object.keys(res.hf)) {
            const rawIncoming = res.hf[k] || {};
            const normalizedStatus =
              rawIncoming.status === "completed" ? "installed" : rawIncoming.status;
            const incoming =
              normalizedStatus !== rawIncoming.status
                ? { ...rawIncoming, status: normalizedStatus }
                : rawIncoming;
            const existing = nextInfo[k] || {};
            if (existing.status === "deleting") continue;
            if (incoming.status === "installed" && existing.status !== "installed") {
              newlyCompletedHf = true;
              hfStateGuardRef.current[k] = { state: "installed", timestamp: Date.now() };
            }
            const isDownloading = incoming.status === "downloading" && existing.status === "downloading";
            const clampedProg =
              isDownloading && typeof incoming.progress === "number" && typeof existing.progress === "number"
                ? Math.max(existing.progress, incoming.progress)
                : incoming.progress;
            nextInfo[k] = {
              ...existing,
              ...incoming,
              ...(clampedProg !== undefined ? { progress: clampedProg } : {}),
            };
          }
          return nextInfo;
        });
        if (newlyCompletedHf) {
          coreStateEpochRef.current += 1;
          checkModules(true, true);
        }
      }

      if (res.ollama_install) {
        setOllamaInstallProgressRef.current((prev) => ({ ...prev, ...res.ollama_install }));
      }
    };

    let progressInterval = setInterval(async () => {
      if (eventBus.isConnected()) return;
      try {
        let res = await clientApi.getDownloadsProgress();
        applyDownloadsProgress(res);
      } catch {}
    }, 800);

    const unsubscribeBus = eventBus.subscribe((payload) => {
      if (!payload) return;
      if (payload.type === "custom_event") {
        if (payload.event_name === "downloads_progress" && payload.payload) {
          applyDownloadsProgress(payload.payload);
        } else if (payload.event_name === "core_engine_progress") {
          const data = payload.payload || payload.data;
          if (data && handleCoreEngineProgressRef.current) {
            handleCoreEngineProgressRef.current(data);
          }
        } else if (payload.event_name === "model_download_progress" && payload.payload) {
          const { key, data } = payload.payload;
          if (key && data) {
            const normalizedStatus =
              data.status === "completed"
                ? "installed"
                : data.status === "cancelled"
                ? "missing"
                : data.status;
            const normalizedData =
              normalizedStatus !== data.status
                ? {
                    ...data,
                    status: normalizedStatus,
                    ...(data.status === "cancelled" ? { progress: 0, speed_mbps: 0, eta_seconds: 0 } : {}),
                  }
                : data;

            if (normalizedStatus === "installed") {
              handleHFStateChange([key], "installed");
            } else if (data.status === "cancelled" || normalizedStatus === "error") {
              handleHFStateChange([key], "missing");
            } else if (normalizedStatus === "downloading") {
              hfStateGuardRef.current[key] = { state: "downloading", timestamp: Date.now() };
            }

            setOllamaModelsInfo((prev) => {
              const existing = prev[key] || {};
              if (existing.status === "deleting") return prev;
              const isDownloading =
                normalizedData.status === "downloading" && existing.status === "downloading";
              const clampedProg =
                isDownloading &&
                typeof normalizedData.progress === "number" &&
                typeof existing.progress === "number"
                  ? Math.max(existing.progress, normalizedData.progress)
                  : normalizedData.progress;
              return {
                ...prev,
                [key]: {
                  ...existing,
                  ...normalizedData,
                  ...(clampedProg !== undefined ? { progress: clampedProg } : {}),
                },
              };
            });
            if (
              normalizedStatus === "installed" ||
              data.status === "cancelled" ||
              (typeof normalizedData.progress === "number" && normalizedData.progress >= 100)
            ) {
              checkModules(true, true);
            }
          }
        } else if (
          payload.event_name === "model_inventory_changed" ||
          payload.event_name === "ollama_model_deleted" ||
          payload.event_name === "models_updated"
        ) {
          checkModules(true, true);
        } else if (payload.event_name === "ollama_install_progress") {
          const data = payload.payload || payload.data;
          if (data) {
            setOllamaInstallProgressRef.current(data);
            if (data.status === "completed") {
              addToastRef.current("Motor Ollama instalado com sucesso! Iniciando serviço...", "success");
              checkModules(true, true);
            } else if (data.status === "error") {
              addToastRef.current(data.error || data.message || "Erro na instalação do Ollama.", "error");
              checkModules(true, true);
            }
          }
        }
      }
    });

    return () => {
      clearInterval(hwInterval);
      clearInterval(statusInterval);
      clearInterval(progressInterval);
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", handleVisibilityChange);
      }
      unsubscribeBus();
    };
  }, [
    isActive,
    checkModules,
    fetchHardwareTelemetry,
    handleHFStateChange,
    setOllamaModelsInfo,
    setOllamaModelsTags,
    moduleStatusRef,
    ollamaModelsCountRef,
    hfStateGuardRef,
    coreStateEpochRef,
    handleCoreEngineProgressRef,
    setOllamaInstallProgressRef,
    addToastRef,
  ]);
}
