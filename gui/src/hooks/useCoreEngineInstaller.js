import { useRef, useCallback, useEffect } from "react";
import { clientApi } from "../api/bridge";

/**
 * Hook especializado na instalação/desinstalação do motor central de IA (PyTorch / GPU)
 * e liberação de cache de VRAM.
 */
export function useCoreEngineInstaller({
  setOllamaModelsTags,
  setModuleStatus,
  checkModules,
  addToast,
  setHardwareStats,
  onCoreStateChange,
}) {
  const installProgressIntervalRef = useRef(null);
  const activeOperationRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (installProgressIntervalRef.current) {
      clearInterval(installProgressIntervalRef.current);
      installProgressIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  const clearVRAM = useCallback(async () => {
    try {
      await clientApi.clearVRAM();
      addToast(`Cache de VRAM e memória liberados com sucesso.`, `success`);
      let hw = await clientApi.getHardwareStats();
      if (hw && setHardwareStats) setHardwareStats(hw);
      checkModules(true, false);
    } catch (err) {
      console.error(err);
      addToast(`Erro ao liberar VRAM.`, `error`);
    }
  }, [addToast, checkModules, setHardwareStats]);

  const applyCoreProgressPayload = useCallback((progRes, fallbackMode = null) => {
    if (!progRes) return;
    const mode = activeOperationRef.current || fallbackMode || (progRes.status === "uninstalling" ? "uninstall" : "install");
    if (!activeOperationRef.current && progRes.status !== "installing" && progRes.status !== "uninstalling") {
      return;
    }

    const logs = (progRes.log || ``).split(`\n`).filter((l) => l.trim().length > 0);
    const defaultMsg = mode === "uninstall" ? `Desinstalando pacotes...` : `Instalando dependências...`;
    const lastLog = logs[logs.length - 1] || defaultMsg;
    const rawPercent = typeof progRes.percent === `number` ? progRes.percent : (mode === "uninstall" ? 5 : 0);
    const msg = progRes.message || lastLog;

    if (progRes.status === `completed` || progRes.status === `error`) {
      if (!activeOperationRef.current) return;
      activeOperationRef.current = null;
      stopPolling();

      if (mode === "uninstall") {
        if (progRes.status === `completed`) {
          if (onCoreStateChange) onCoreStateChange("not_installed");
          addToast(`PyTorch desinstalado com sucesso.`, `success`);
          if (setModuleStatus) {
            setModuleStatus((prev) => ({
              ...prev,
              ocr: { state: "not_installed" },
              cuda: { state: "not_installed" },
            }));
          }
          try {
            const cached = localStorage.getItem("visionary:cached_module_status");
            if (cached) {
              const parsed = JSON.parse(cached);
              parsed.ocr = { state: "not_installed" };
              parsed.cuda = { state: "not_installed" };
              localStorage.setItem("visionary:cached_module_status", JSON.stringify(parsed));
            }
          } catch {}
        } else {
          if (onCoreStateChange) onCoreStateChange(null);
          addToast(progRes.message || `Erro na desinstalação do PyTorch.`, `error`);
        }
        setOllamaModelsTags((prev) => {
          let nextTags = { ...prev };
          delete nextTags.ocr;
          return nextTags;
        });
        checkModules(true, true);
        return;
      }

      if (progRes.status === `completed`) {
        if (onCoreStateChange) onCoreStateChange("installed");
        if (!progRes.message?.includes("já instalado")) {
          addToast(`Motor de IA instalado com sucesso!`, `success`);
        }
        if (setModuleStatus) {
          setModuleStatus((prev) => ({
            ...prev,
            ocr: { state: "installed" },
            cuda: { state: "installed" },
          }));
        }
        try {
          const cached = localStorage.getItem("visionary:cached_module_status");
          if (cached) {
            const parsed = JSON.parse(cached);
            parsed.ocr = { state: "installed" };
            parsed.cuda = { state: "installed" };
            localStorage.setItem("visionary:cached_module_status", JSON.stringify(parsed));
          }
        } catch {}
      } else {
        if (onCoreStateChange) onCoreStateChange(null);
        addToast(progRes.message || `Erro na instalação do motor.`, `error`);
      }
      setOllamaModelsTags((prev) => {
        let nextTags = { ...prev };
        delete nextTags.ocr;
        return nextTags;
      });
      checkModules(true, true);
      return;
    }

    setOllamaModelsTags((prev) => {
      const prevPct = typeof prev.ocr?.progress === "number" ? prev.ocr.progress : 0;
      const monotonicPct = Math.min(99.5, Math.max(prevPct, rawPercent));
      return {
        ...prev,
        ocr: {
          mode,
          progress: monotonicPct,
          text: msg,
          speed_mbps: progRes.speed_mbps || 0,
          eta_seconds: progRes.eta_seconds || 0,
          downloaded_bytes: progRes.downloaded_bytes || 0,
          total_bytes: progRes.total_bytes || 0,
        },
      };
    });
  }, [addToast, checkModules, onCoreStateChange, setModuleStatus, setOllamaModelsTags, stopPolling]);

  const installCoreEngine = useCallback(async () => {
    activeOperationRef.current = "install";
    if (onCoreStateChange) onCoreStateChange("installing");
    setOllamaModelsTags((prev) => ({
      ...prev,
      ocr: { mode: "install", progress: 0, text: `Resolvendo pacotes PyTorch...` },
    }));
    try {
      let res = await clientApi.installCoreEngine();
      if (res && res.success === false) {
        activeOperationRef.current = null;
        if (onCoreStateChange) onCoreStateChange(null);
        addToast(res.message || `Erro ao iniciar instalação.`, `error`);
        setOllamaModelsTags((prev) => {
          let nextTags = { ...prev };
          delete nextTags.ocr;
          return nextTags;
        });
        return;
      }
      if (res?.already_installed || (res?.message && res.message.includes("já está instalado"))) {
        activeOperationRef.current = null;
        if (onCoreStateChange) onCoreStateChange("installed");
        addToast(res.message, `info`);
        setOllamaModelsTags((prev) => {
          let nextTags = { ...prev };
          delete nextTags.ocr;
          return nextTags;
        });
        if (setModuleStatus) {
          setModuleStatus((prev) => ({
            ...prev,
            ocr: { state: "installed" },
            cuda: { state: "installed" },
          }));
        }
        try {
          const cached = localStorage.getItem("visionary:cached_module_status");
          if (cached) {
            const parsed = JSON.parse(cached);
            parsed.ocr = { state: "installed" };
            parsed.cuda = { state: "installed" };
            localStorage.setItem("visionary:cached_module_status", JSON.stringify(parsed));
          }
        } catch {}
        checkModules(true, true);
        return;
      }
      let failCount = 0;
      stopPolling();
      installProgressIntervalRef.current = setInterval(async () => {
        try {
          let progRes = await clientApi.getInstallProgress();
          failCount = 0;
          applyCoreProgressPayload(progRes, "install");
        } catch {
          failCount++;
          if (failCount > 10) {
            activeOperationRef.current = null;
            if (onCoreStateChange) onCoreStateChange(null);
            stopPolling();
            addToast(`Perda de comunicação com o backend durante a instalação.`, `error`);
            setOllamaModelsTags((prev) => {
              let nextTags = { ...prev };
              delete nextTags.ocr;
              return nextTags;
            });
            checkModules(true, true);
          }
        }
      }, 400);
    } catch (err) {
      activeOperationRef.current = null;
      if (onCoreStateChange) onCoreStateChange(null);
      console.error(`Erro ao chamar installCoreEngine:`, err);
      addToast(`Falha ao conectar com o serviço de instalação do motor.`, `error`);
      setOllamaModelsTags((prev) => {
        let nextTags = { ...prev };
        delete nextTags.ocr;
        return nextTags;
      });
      checkModules(true, true);
    }
  }, [addToast, applyCoreProgressPayload, checkModules, onCoreStateChange, setModuleStatus, setOllamaModelsTags, stopPolling]);

  const uninstallCoreEngine = useCallback(async () => {
    activeOperationRef.current = "uninstall";
    if (onCoreStateChange) onCoreStateChange("uninstalling");
    setOllamaModelsTags((prev) => ({
      ...prev,
      ocr: { mode: "uninstall", progress: 5, text: `Desinstalando PyTorch...` },
    }));
    try {
      let res = await clientApi.uninstallCoreEngine();
      if (res && res.success) {
        stopPolling();
        installProgressIntervalRef.current = setInterval(async () => {
          try {
            let progRes = await clientApi.getInstallProgress();
            applyCoreProgressPayload(progRes, "uninstall");
          } catch {}
        }, 400);
      } else {
        activeOperationRef.current = null;
        if (onCoreStateChange) onCoreStateChange(null);
        addToast(res?.message || `Erro ao iniciar desinstalação.`, `error`);
        setOllamaModelsTags((prev) => {
          let nextTags = { ...prev };
          delete nextTags.ocr;
          return nextTags;
        });
      }
    } catch {
      activeOperationRef.current = null;
      if (onCoreStateChange) onCoreStateChange(null);
      addToast(`Erro ao desinstalar PyTorch.`, `error`);
      setOllamaModelsTags((prev) => {
        let nextTags = { ...prev };
        delete nextTags.ocr;
        return nextTags;
      });
    }
  }, [addToast, applyCoreProgressPayload, onCoreStateChange, setOllamaModelsTags, stopPolling]);

  return {
    installCoreEngine,
    uninstallCoreEngine,
    clearVRAM,
    handleCoreEngineProgress: applyCoreProgressPayload,
  };
}
