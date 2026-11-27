import { useCallback } from "react";
import { clientApi } from "../api/bridge";

/**
 * Hook especializado em download e deleção de modelos HuggingFace (Florence-2, Comic-YOLO, etc.).
 */
export function useHFEngineManager({
  addToast,
  checkModules,
  setIsCheckingOllama,
  setOllamaDownloads,
  setOllamaModelsInfo,
  onHFStateChange,
}) {
  const downloadHFModel = useCallback(async (modelId, modelTitle) => {
    setOllamaDownloads((prev) => ({ ...prev, [modelId]: true }));
    if (onHFStateChange) onHFStateChange([modelId], "downloading");
    if (setOllamaModelsInfo) {
      setOllamaModelsInfo((prev) => ({
        ...prev,
        [modelId]: {
          ...(prev[modelId] || {}),
          status: "downloading",
          progress: Number(prev[modelId]?.progress) || 0,
          speed_mbps: 0,
          eta_seconds: 0,
          message: "Sincronizando manifesto HF...",
        },
      }));
    }
    try {
      let res = await clientApi.downloadHuggingFaceModel(modelId);
      if (res && res.success) {
        addToast(`Iniciando download de ${modelTitle}...`, `success`);
        checkModules(true, false);
      } else {
        if (onHFStateChange) onHFStateChange([modelId], null);
        if (setOllamaModelsInfo) {
          setOllamaModelsInfo((prev) => ({
            ...prev,
            [modelId]: { ...(prev[modelId] || {}), status: "missing", progress: 0 },
          }));
        }
      }
    } catch {
      if (onHFStateChange) onHFStateChange([modelId], null);
      if (setOllamaModelsInfo) {
        setOllamaModelsInfo((prev) => ({
          ...prev,
          [modelId]: { ...(prev[modelId] || {}), status: "missing", progress: 0 },
        }));
      }
    }
    setOllamaDownloads((prev) => ({ ...prev, [modelId]: false }));
  }, [addToast, checkModules, onHFStateChange, setOllamaDownloads, setOllamaModelsInfo]);

  const deleteHFModel = useCallback(async (modelId, modelTitle) => {
    setIsCheckingOllama(true);
    const targetIds = modelId.startsWith("florence2") ? ["florence2", "florence2_large"] : [modelId];
    if (onHFStateChange) onHFStateChange(targetIds, "deleting");

    // 1. Feedback visual imediato: exibe estado explícito de remoção
    if (setOllamaModelsInfo) {
      if (modelId.startsWith("florence2")) {
        setOllamaModelsInfo((prev) => ({
          ...prev,
          florence2: { ...(prev.florence2 || {}), status: "deleting", message: "Removendo do disco..." },
          florence2_large: { ...(prev.florence2_large || {}), status: "deleting", message: "Removendo do disco..." },
        }));
      } else {
        setOllamaModelsInfo((prev) => ({
          ...prev,
          [modelId]: { ...(prev[modelId] || {}), status: "deleting", message: "Removendo do disco..." },
        }));
      }
    }

    try {
      let res;
      if (modelId.startsWith("florence2")) {
        const results = await Promise.allSettled([
          clientApi.deleteHuggingFaceModel("florence2_large"),
          clientApi.deleteHuggingFaceModel("florence2"),
        ]);
        const allOk = results.every((r) => r.status === "fulfilled" && r.value?.success !== false);
        res = { success: allOk };
      } else {
        res = await clientApi.deleteHuggingFaceModel(modelId);
      }

      if (res && res.success !== false) {
        if (onHFStateChange) onHFStateChange(targetIds, "missing");
        addToast(`Modelo ${modelTitle} removido com sucesso!`, `success`);
        if (setOllamaModelsInfo) {
          if (modelId.startsWith("florence2")) {
            setOllamaModelsInfo((prev) => ({
              ...prev,
              florence2: { ...(prev.florence2 || {}), status: "missing", progress: 0 },
              florence2_large: { ...(prev.florence2_large || {}), status: "missing", progress: 0 },
            }));
          } else {
            setOllamaModelsInfo((prev) => ({
              ...prev,
              [modelId]: { ...(prev[modelId] || {}), status: "missing", progress: 0 },
            }));
          }
        }
        try {
          const cached = localStorage.getItem("visionary:cached_ollama_info");
          if (cached) {
            const parsed = JSON.parse(cached);
            if (modelId.startsWith("florence2")) {
              if (parsed.florence2) parsed.florence2.status = "missing";
              if (parsed.florence2_large) parsed.florence2_large.status = "missing";
            } else if (parsed[modelId]) {
              parsed[modelId].status = "missing";
            }
            localStorage.setItem("visionary:cached_ollama_info", JSON.stringify(parsed));
          }
        } catch {}
      } else {
        if (onHFStateChange) onHFStateChange(targetIds, null);
        addToast(res?.error || `Não foi possível remover ${modelTitle}. Arquivos podem estar em uso.`, `error`);
      }
    } catch (err) {
      if (onHFStateChange) onHFStateChange(targetIds, null);
      console.error(err);
      addToast(`Erro ao remover modelo ${modelTitle}.`, `error`);
    } finally {
      await checkModules(true, true);
      setIsCheckingOllama(false);
    }
  }, [addToast, checkModules, onHFStateChange, setIsCheckingOllama, setOllamaModelsInfo]);

  const cancelHFModel = useCallback(async (modelId, modelTitle) => {
    const targetIds = modelId.startsWith("florence2") ? ["florence2", "florence2_large"] : [modelId];
    try {
      let res = await clientApi.cancelHuggingFaceModel(modelId);
      if (res && res.success) {
        if (onHFStateChange) onHFStateChange(targetIds, "missing");
        if (setOllamaModelsInfo) {
          setOllamaModelsInfo((prev) => {
            const next = { ...prev };
            for (const id of targetIds) {
              if (next[id]?.status === "downloading") {
                next[id] = {
                  ...next[id],
                  status: "missing",
                  progress: 0,
                  speed_mbps: 0,
                  eta_seconds: 0,
                  message: "Download cancelado.",
                };
              }
            }
            return next;
          });
        }
        addToast(`Download de ${modelTitle} cancelado.`, `info`);
        await checkModules(true, true);
      }
    } catch (err) {
      console.error(err);
    }
    setOllamaDownloads((prev) => ({ ...prev, [modelId]: false }));
  }, [addToast, checkModules, onHFStateChange, setOllamaDownloads, setOllamaModelsInfo]);

  return {
    downloadHFModel,
    deleteHFModel,
    cancelHFModel,
  };
}
