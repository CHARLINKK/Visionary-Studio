import { useState, useEffect, useCallback, useMemo } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useToast } from '../contexts/ToastContext';
import { clientApi } from '../api/bridge.js';

export function useStudioBatchRunner({
  folderPath,
  folderName,
  pages,
  selectedPages,
  activePage,
  fetchDirectory,
  setRefreshTrigger,
}) {
  const { addToast } = useToast();
  const [steps, setSteps] = useState({ layout: true, ocr: true, translate: true });
  const [deepValidation, setDeepValidation] = useState(false);
  const [overwrite, setOverwrite] = useState(false);
  const [tone, setTone] = useState('Neutro');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [clearConfirmState, setClearConfirmState] = useState(null);
  const [isClearing, setIsClearing] = useState(false);

  const addJob = useWorkspaceStore(state => state.addJob);
  const updateJob = useWorkspaceStore(state => state.updateJob);
  const bumpExplorerRevision = useWorkspaceStore(state => state.bumpExplorerRevision);
  const setIsClearingData = useWorkspaceStore(state => state.setIsClearingData);
  const triggerDataCleared = useWorkspaceStore(state => state.triggerDataCleared);

  useEffect(() => {
    clientApi.getSettings().then(settings => {
      if (settings?.pipeline_steps) setSteps(settings.pipeline_steps);
      if (settings?.translation_tone) {
        setTone(settings.translation_tone === 'neutral' ? 'Neutro' : settings.translation_tone);
      }
    }).catch(() => {});
  }, []);

  const pagesToCheck = useMemo(() => {
    return selectedPages.size > 0
      ? pages.filter((_, i) => selectedPages.has(i))
      : (activePage ? [activePage] : []);
  }, [selectedPages, pages, activePage]);

  const hasLayoutInJson = pagesToCheck.length > 0 && pagesToCheck.every(p => p.pageData && p.pageData.layout);
  const hasOcrInJson = pagesToCheck.length > 0 && pagesToCheck.every(p => p.pageData && (p.pageData.ocr || p.pageData.blockCount === 0));

  const canRunOcr = hasLayoutInJson;
  const canRunTranslate = hasOcrInJson;

  const handleProcess = useCallback(async (stepsOverride = null) => {
    const currentSteps = stepsOverride || steps;
    const selectedFiles = Array.from(selectedPages).map(i => pages[i]);
    if (selectedFiles.length === 0) return;

    setIsSubmitting(true);
    try {
      let activeModel = null;
      let settings = null;
      let modelsStatus = null;
      let modulesStatus = null;

      try {
        const [s, m, mod] = await Promise.all([
          clientApi.getSettings().catch(() => null),
          clientApi.getModelsStatus().catch(() => null),
          clientApi.checkModulesStatus().catch(() => null)
        ]);
        settings = s;
        modelsStatus = m;
        modulesStatus = mod;
        if (settings?.selected_models?.transPol) {
          activeModel = settings.selected_models.transPol;
        } else if (Array.isArray(modelsStatus?.ollama_models) && modelsStatus.ollama_models.length > 0) {
          const firstInstalled = modelsStatus.ollama_models[0];
          activeModel = typeof firstInstalled === 'string' ? firstInstalled : firstInstalled?.name;
          if (activeModel) {
            clientApi.saveSettings({
              selected_models: { ...(settings?.selected_models || {}), transPol: activeModel }
            }).catch(() => {});
          }
        }
      } catch {}

      if (currentSteps.translate) {
        if (!activeModel) {
          addToast("Nenhum modelo de Tradução selecionado. Baixe um modelo na Central de Módulos antes de processar!", "error");
          return;
        }
        const installedOllamaList = Array.isArray(modelsStatus?.ollama_models) ? modelsStatus.ollama_models : [];
        const isModelPresentOnDisk = installedOllamaList.some((m) => {
          const mName = typeof m === 'string' ? m : m?.name;
          return mName === activeModel || (mName && activeModel && mName.split(':')[0] === activeModel.split(':')[0]);
        });
        if (!isModelPresentOnDisk) {
          addToast(`O modelo de tradução '${activeModel}' não está baixado no Ollama. Baixe-o na Central de Módulos antes de processar!`, "error");
          return;
        }
      }

      if (currentSteps.layout || currentSteps.ocr) {
        if (modulesStatus?.ocr?.state === 'installing') {
          addToast("O motor PyTorch Core está sendo instalado no momento. Aguarde a conclusão antes de executar.", "warning");
          return;
        }
        if (modulesStatus?.ocr?.state === 'not_installed') {
          addToast("O motor PyTorch Core não está instalado. Instale-o na Central de Módulos antes de executar.", "error");
          return;
        }
      }

      if (currentSteps.layout && modelsStatus?.yolo_detector?.status !== 'installed') {
        addToast("Erro crítico: O Modelo Espacial (YOLO) não está baixado. Baixe-o na Central de Módulos (Passo 2).", "error");
        return;
      }
      const isFlorenceInstalled =
        modelsStatus?.florence2?.status === 'installed' ||
        modelsStatus?.florence2_large?.status === 'installed';
      if (currentSteps.ocr && !isFlorenceInstalled) {
        addToast("Erro crítico: O Modelo de Visão (Florence-2) não está baixado. Baixe-o na Central de Módulos (Passo 2).", "error");
        return;
      }

      const effectiveSteps = {
        layout: currentSteps.layout,
        ocr: currentSteps.ocr && (currentSteps.layout || hasLayoutInJson),
        translate: currentSteps.translate && (currentSteps.ocr || hasOcrInJson)
      };

      const jobId = 'job_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

      addJob({
        id: jobId,
        type: 'batch',
        status: 'running',
        progress: 0,
        currentStepLabel: 'Iniciando pipeline...',
        logs: [`[${new Date().toLocaleTimeString('pt-BR')}] [SISTEMA] Iniciando lote de ${selectedFiles.length} páginas...`],
        payload: { 
          chapterName: folderName || 'Lote',
          folderPath: folderPath,
          isPauseJob: currentSteps.pauseOcr,
          firstPageIndex: Array.from(selectedPages).sort((a,b)=>a-b)[0]
        }
      });
      addToast("Processamento iniciado!", "success");

      const res = await clientApi.queueJob({
        job_id: jobId,
        type: 'batch',
        folderPath,
        files: selectedFiles.map(f => f?.path).filter(Boolean),
        steps: effectiveSteps,
        tone,
        model: activeModel,
        resumeFromLayout: false,
        deepValidation,
        overwrite
      });

      if (!res || !res.success) {
        const errMsg = res?.error || "Falha ao iniciar no backend";
        updateJob(jobId, { status: 'failed', error: errMsg, currentStepLabel: 'Erro ao iniciar' });
        addToast("Erro do backend: " + errMsg, "error");
      }
    } catch (e) {
      addToast("Erro ao contatar backend: " + e.message, "error");
    } finally {
      setIsSubmitting(false);
    }
  }, [
    steps, selectedPages, pages, folderName, folderPath, tone, deepValidation, overwrite,
    hasLayoutInJson, hasOcrInJson, addJob, updateJob, addToast
  ]);

  const requestClear = useCallback((stages) => {
    const selectedPaths = Array.from(selectedPages).map(i => pages[i]?.path).filter(Boolean);
    if (selectedPaths.length === 0) return;

    const count = selectedPaths.length;
    let title = "Limpar Dados?";
    let message = count > 1 ? `Quer limpar os dados de ${count} páginas?` : "Quer limpar os dados dessa página?";
    let confirmText = "Limpar";

    if (stages.length === 1 && stages[0] === 'translate') {
      title = "Limpar Traduções?";
      message = count > 1 
        ? `Quer apagar as traduções de ${count} páginas? O OCR e os balões continuam salvos.` 
        : "Quer apagar as traduções dessa página? O texto original do OCR e os balões continuam salvos.";
      confirmText = "Limpar Traduções";
    } else if (stages.includes('ocr') && !stages.includes('layout')) {
      title = "Limpar OCR?";
      message = count > 1 
        ? `Quer resetar o OCR de ${count} páginas? Os balões de layout continuam salvos pra você rodar de novo.` 
        : "Quer limpar o texto lido dessa página? Os balões de layout continuam salvos pra você rodar de novo quando quiser.";
      confirmText = "Limpar OCR";
    } else if (stages.includes('layout')) {
      title = count > 1 ? "Recomeçar Páginas?" : "Recomeçar Página?";
      message = count > 1 
        ? `Quer apagar os balões e textos de ${count} páginas pra recomeçar do zero? As imagens continuam intactas.` 
        : "Quer apagar os balões e textos dessa página pra recomeçar do zero? A imagem original continua intacta.";
      confirmText = "Recomeçar";
    }

    setClearConfirmState({ stages, title, message, confirmText });
  }, [selectedPages, pages]);

  const executeClear = useCallback(async () => {
    if (!clearConfirmState) return;
    const { stages } = clearConfirmState;
    setClearConfirmState(null);

    const selectedPaths = Array.from(selectedPages).map(i => pages[i]?.path).filter(Boolean);
    if (selectedPaths.length === 0) return;

    setIsClearingData(true);
    setIsClearing(true);
    triggerDataCleared(selectedPaths, stages);

    try {
      const res = await clientApi.clearPageData(selectedPaths, stages);
      if (res && res.success) {
        addToast(res.message, "success");
        setRefreshTrigger(prev => prev + 1);
        fetchDirectory(false, false);
        bumpExplorerRevision();
      } else {
        addToast("Erro ao limpar dados: " + (res?.error || "Desconhecido"), "error");
      }
    } catch (err) {
      addToast("Exceção ao limpar dados: " + (err?.message || String(err)), "error");
    } finally {
      setIsClearingData(false);
      setIsClearing(false);
    }
  }, [
    clearConfirmState, selectedPages, pages, setIsClearingData, triggerDataCleared,
    addToast, setRefreshTrigger, fetchDirectory, bumpExplorerRevision
  ]);

  return {
    steps,
    setSteps,
    deepValidation,
    setDeepValidation,
    overwrite,
    setOverwrite,
    tone,
    setTone,
    isSubmitting,
    clearConfirmState,
    setClearConfirmState,
    isClearing,
    canRunOcr,
    canRunTranslate,
    handleProcess,
    requestClear,
    executeClear,
  };
}
