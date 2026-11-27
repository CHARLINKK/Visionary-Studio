import { useState, useCallback } from "react";
import { clientApi } from "../api/bridge";

/**
 * Hook especializado na gestão de modelos Ollama, ciclo de vida do daemon local
 * e instalação transparente do binário oficial portátil.
 */
export function useOllamaManager({ addToast, setModuleStatus, checkModules }) {
  const [ollamaModels, setOllamaModels] = useState(() => {
    try {
      const cached = localStorage.getItem("visionary:cached_ollama_models");
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  });

  const [ollamaModelsInfo, setOllamaModelsInfo] = useState(() => {
    try {
      const cached = localStorage.getItem("visionary:cached_ollama_info");
      return cached ? JSON.parse(cached) : {};
    } catch {
      return {};
    }
  });

  const [ollamaModelsTags, setOllamaModelsTags] = useState({});
  const [ollamaModelsDetails, setOllamaModelsDetails] = useState(() => {
    try {
      const cached = localStorage.getItem("visionary:cached_ollama_models_details");
      return cached ? JSON.parse(cached) : {};
    } catch {
      return {};
    }
  });
  const [ollamaDownloads, setOllamaDownloads] = useState({});
  const [isCheckingOllama, setIsCheckingOllama] = useState(false);
  const [isOllamaStarting, setIsOllamaStarting] = useState(false);
  const [ollamaInstallProgress, setOllamaInstallProgress] = useState({
    status: "idle",
    percent: 0,
    downloaded_bytes: 0,
    total_bytes: 0,
    speed_mbps: 0,
    eta_seconds: 0,
    message: "",
    error: "",
  });

  const isOllamaInstalling =
    ollamaInstallProgress.status === "downloading" ||
    ollamaInstallProgress.status === "extracting";

  const installIsolatedOllama = useCallback(async () => {
    if (isOllamaInstalling) return;
    setOllamaInstallProgress((prev) => ({
      ...prev,
      status: "downloading",
      percent: 0,
      message: "Conectando ao repositório oficial do Ollama...",
    }));
    addToast("Iniciando download do motor Ollama portátil...", "info");
    try {
      const res = await clientApi.installIsolatedOllama();
      if (!res?.success) {
        addToast(res?.message || "Não foi possível iniciar o download do Ollama.", "error");
        setOllamaInstallProgress((prev) => ({ ...prev, status: "error", error: res?.message }));
      }
    } catch (err) {
      addToast("Erro ao solicitar download do Ollama.", "error");
      setOllamaInstallProgress((prev) => ({ ...prev, status: "error", error: err?.message }));
    }
  }, [addToast, isOllamaInstalling]);

  const cancelIsolatedOllamaInstall = useCallback(async () => {
    try {
      await clientApi.cancelIsolatedOllamaInstall();
      addToast("Download do motor Ollama cancelado.", "info");
    } catch (_) {}
    setOllamaInstallProgress((prev) => ({ ...prev, status: "cancelled", message: "Cancelado." }));
    await checkModules();
  }, [addToast, checkModules]);

  const startOllamaService = useCallback(async () => {
    if (isOllamaStarting) return;
    setIsOllamaStarting(true);
    addToast(`Iniciando serviço Ollama via Motor Isolado...`, `info`);
    try {
      let res = await clientApi.startOllamaServer();
      if (res && res.success) {
        if (res.models && res.models.length > 0) setOllamaModels(res.models);
        setModuleStatus((prev) => ({
          ...prev,
          ollama: { state: `installed_and_running` },
        }));
        addToast(res.message || `Ollama iniciado com sucesso!`, `success`);
      } else {
        addToast(res?.error || `Não foi possível iniciar o Ollama automaticamente.`, `error`);
      }
    } catch {
      addToast(`Erro ao iniciar Ollama.`, `error`);
    }
    for (let i = 0; i < 6; i++) {
      try {
        let statusRes = await clientApi.checkModulesStatus();
        if (statusRes && statusRes.ollama?.state === `installed_and_running`) {
          setModuleStatus((prev) => ({
            ...prev,
            ollama: statusRes.ollama,
          }));
          if (statusRes.ollamaModels) setOllamaModels(statusRes.ollamaModels);
          break;
        }
      } catch {}
      await new Promise((resolve) => setTimeout(resolve, 350));
    }
    await checkModules();
    setIsOllamaStarting(false);
  }, [addToast, checkModules, isOllamaStarting, setModuleStatus]);

  const pullOllamaModel = useCallback(async (modelName, currentOllamaState) => {
    if (!modelName || !modelName.trim()) return;
    let name = modelName.trim();
    if (currentOllamaState !== `installed_and_running`) {
      await startOllamaService();
    }
    setOllamaModelsTags((prev) => ({
      ...prev,
      [name]: { progress: 0, text: "Iniciando download...", status: "downloading" },
    }));
    try {
      let res = await clientApi.pullOllamaModel(name);
      if (res && res.success) {
        addToast(`Iniciando download do modelo ${name}...`, `info`);
      } else {
        addToast(res?.message || `Falha ao iniciar download de ${name}.`, `error`);
        setOllamaModelsTags((prev) => {
          const next = { ...prev };
          delete next[name];
          return next;
        });
      }
    } catch {
      addToast(`Erro de conexão ao baixar ${name}.`, `error`);
      setOllamaModelsTags((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
    checkModules(true, false);
  }, [addToast, checkModules, startOllamaService]);

  const deleteOllamaModel = useCallback(async (modelName) => {
    if (!modelName) return;
    setIsCheckingOllama(true);

    const baseName = modelName.includes(":") ? modelName.split(":")[0] : modelName;

    // 1. Atualização Otimista Imediata da UI
    setOllamaModels((prev) => {
      const next = prev.filter(
        (m) => m !== modelName && m !== `${baseName}:latest` && m !== baseName
      );
      try {
        localStorage.setItem("visionary:cached_ollama_models", JSON.stringify(next));
      } catch {}
      return next;
    });

    setOllamaModelsDetails((prev) => {
      const next = { ...prev };
      delete next[modelName];
      delete next[`${baseName}:latest`];
      delete next[baseName];
      try {
        localStorage.setItem("visionary:cached_ollama_models_details", JSON.stringify(next));
      } catch {}
      return next;
    });

    setOllamaModelsTags((prev) => {
      const next = { ...prev };
      delete next[modelName];
      delete next[`${baseName}:latest`];
      delete next[baseName];
      return next;
    });

    try {
      let res = await clientApi.deleteOllamaModel(modelName);
      if (res && res.success) {
        addToast(`Modelo ${modelName} removido do disco!`, `success`);
      } else {
        addToast(`Erro ao remover: ${res?.error || `falha`}`, `error`);
      }
    } catch {
      addToast(`Erro de conexão ao remover ${modelName}.`, `error`);
    } finally {
      await checkModules(true, true);
      setIsCheckingOllama(false);
    }
  }, [addToast, checkModules, setIsCheckingOllama, setOllamaModels, setOllamaModelsDetails, setOllamaModelsTags]);

  const cancelOllamaDownload = useCallback(async (modelId) => {
    const baseName = modelId.includes(":") ? modelId.split(":")[0] : modelId;
    setOllamaModelsTags((prev) => {
      const next = { ...prev };
      delete next[modelId];
      delete next[`${baseName}:latest`];
      delete next[baseName];
      return next;
    });
    try {
      await clientApi.cancelOllamaDownload(modelId);
      addToast(`Download de ${modelId} cancelado.`, `info`);
    } catch {}
    await checkModules(true, true);
  }, [addToast, checkModules]);

  return {
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
    pullOllamaModel,
    deleteOllamaModel,
    cancelOllamaDownload,
    ollamaInstallProgress,
    setOllamaInstallProgress,
    isOllamaInstalling,
    installIsolatedOllama,
    cancelIsolatedOllamaInstall,
  };
}
