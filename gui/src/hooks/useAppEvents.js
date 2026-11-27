import { useEffect } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { getServerUrl, setServerUrl, clientApi, eventBus } from '../api/bridge';

export function useAppEvents(
  setActiveTab, 
  setSelectedFolder, 
  setIsDevUnlocked, 
  selectedFolder, 
  addToast
) {
  // Health Check
  useEffect(() => {
    const checkHealth = async () => {
      try {
        let serverUrl = getServerUrl() || 'http://127.0.0.1:5000';
        const res = await fetch(`${serverUrl}/api/health`);
        if (res.ok) {
          const data = await res.json();
          if (!data.disk_write) addToast('Aviso de Disco: Sem permissão de gravação no diretório base.', 'error', 10000);
          if (!data.pytorch_cuda) addToast('PyTorch CUDA Offline: Visão funcionará via CPU (Lento).', 'warning', 8000);
        }
      } catch {}
    };
    const timerId = setTimeout(checkHealth, 3000);
    return () => clearTimeout(timerId);
  }, [addToast]);

  // Sincronização reativa entre activeChapterPath do store e o estado local do Explorer
  useEffect(() => {
    return useWorkspaceStore.subscribe((state) => {
      if (state.activeChapterPath && state.activeChapterPath !== selectedFolder?.path) {
        setSelectedFolder({ path: state.activeChapterPath, name: state.activeChapterName });
      }
    });
  }, [selectedFolder?.path, setSelectedFolder]);

  // Tab switching e comandos do Electron Shell / Bandeja (Tray)
  useEffect(() => {
    let unsubNotify = null;
    if (window.electronAPI?.onNotificationClicked) {
      unsubNotify = window.electronAPI.onNotificationClicked((data) => {
        if (data?.actionTab) {
          setActiveTab(data.actionTab);
        }
      });
    }

    const handleNavigateAction = (rawAction) => {
      if (!rawAction) return;
      let action = String(rawAction).toLowerCase().trim().replace(/^['"]|['"]$/g, '');
      if (action === 'estudio' || action === 'studio') action = 'processamento';
      if (action === 'library') action = 'biblioteca';
      if (action === 'settings') action = 'configuracoes';
      if (action === 'modules') action = 'modulos';

      if (action === 'queue') {
        setActiveTab?.('processamento');
        useWorkspaceStore.getState().setActiveTab?.('processamento');
        useWorkspaceStore.getState().toggleQueue?.(true);
      } else if (action === 'dev') {
        setIsDevUnlocked?.(true);
        setActiveTab?.('testes');
        useWorkspaceStore.getState().setActiveTab?.('testes');
      } else if (['processamento', 'biblioteca', 'lightbox', 'modulos', 'configuracoes', 'testes'].includes(action)) {
        setActiveTab?.(action);
        useWorkspaceStore.getState().setActiveTab?.(action);
      }
    };

    if (window.electronAPI?.getInitialAction) {
      window.electronAPI.getInitialAction().then((initialTab) => {
        if (initialTab) handleNavigateAction(initialTab);
      }).catch(() => {});
    }

    let unsubNavigate = null;
    if (window.electronAPI?.onNavigateTab) {
      unsubNavigate = window.electronAPI.onNavigateTab((action) => {
        handleNavigateAction(action);
      });
    }

    let unsubCancel = null;
    if (window.electronAPI?.onCancelJobFromTray) {
      unsubCancel = window.electronAPI.onCancelJobFromTray(() => {
        useWorkspaceStore.getState().cancelAllJobs?.(false);
        addToast?.('Lote interrompido pela bandeja do sistema.', 'info');
      });
    }

    let unsubSymbols = null;
    if (window.electronAPI?.onOpenSymbolsFromTray) {
      unsubSymbols = window.electronAPI.onOpenSymbolsFromTray(() => {
        useWorkspaceStore.getState().toggleQuickSymbols();
      });
    }

    let unsubRecent = null;
    if (window.electronAPI?.onOpenRecentChapterFromTray) {
      unsubRecent = window.electronAPI.onOpenRecentChapterFromTray((chapter) => {
        if (chapter?.path) {
          const name = chapter.name || chapter.path.split(/[/\\]/).filter(Boolean).pop();
          setSelectedFolder({ path: chapter.path, name });
          useWorkspaceStore.getState().setActiveChapter?.(chapter.path, name);
          setActiveTab('processamento');
          addToast?.(`Capítulo aberto: ${name}`, 'info');
        }
      });
    }

    let unsubCloseAction = null;
    if (window.electronAPI?.onCloseActionChangedFromTray) {
      unsubCloseAction = window.electronAPI.onCloseActionChangedFromTray((action) => {
        if (['smart', 'tray', 'quit'].includes(action)) {
          clientApi.saveSettings({ close_action: action }).catch(() => {});
          useWorkspaceStore.getState().updateAppSettings?.({ close_action: action });
          const labels = {
            smart: 'Ao fechar (X): Inteligente (Bandeja se processando)',
            tray: 'Ao fechar (X): Sempre minimizar para a Bandeja',
            quit: 'Ao fechar (X): Sempre encerrar aplicativo',
          };
          addToast?.(labels[action] || 'Preferência de fechamento atualizada.', 'info');
        }
      });
    }

    let unsubOllamaStopped = null;
    if (window.electronAPI?.onOllamaStoppedFromTray) {
      unsubOllamaStopped = window.electronAPI.onOllamaStoppedFromTray(() => {
        useWorkspaceStore.getState().bumpOllamaRevision?.();
        addToast?.('Servidor Ollama encerrado e VRAM liberada.', 'success');
      });
    }

    let unsubSidecarStatus = null;
    if (window.electronAPI?.onSidecarStatus) {
      unsubSidecarStatus = window.electronAPI.onSidecarStatus((status) => {
        if (!status || typeof status !== 'object') return;
        const store = useWorkspaceStore.getState();

        if (status.state === 'reconnecting') {
          const attemptInfo = status.attempt ? ` (${status.attempt}/${status.maxAttempts || 3})` : '';
          addToast?.(`Reconectando ao motor local de IA${attemptInfo}...`, 'warning', 5000);
        } else if (status.state === 'online') {
          if (status.serverUrl) {
            setServerUrl(status.serverUrl);
          }
          if (!eventBus.isConnected()) {
            eventBus.connect();
          }
          if (status.reason !== 'initial_boot') {
            // Reconcilia jobs que estavam em execução na instância anterior do processo Python
            const activeQueue = store?.jobQueue || [];
            activeQueue.forEach((j) => {
              if (j.status === 'running' || j.status === 'pending' || j.status === 'queued') {
                store.updateJob?.(j.id, {
                  status: 'failed',
                  error: 'O motor de IA foi reiniciado automaticamente. Reexecute o lote para continuar.',
                  currentStepLabel: 'Interrompido (Motor reiniciado)',
                });
              }
            });
            store?.bumpOllamaRevision?.();
            addToast?.('Motor local de IA recuperado e reconectado com sucesso.', 'success', 5000);
          }
        } else if (status.state === 'failed') {
          const activeQueue = store?.jobQueue || [];
          activeQueue.forEach((j) => {
            if (j.status === 'running' || j.status === 'pending' || j.status === 'queued') {
              store.updateJob?.(j.id, {
                status: 'failed',
                error: status.message || 'Falha crítica no motor Python.',
                currentStepLabel: 'Erro no motor de IA',
              });
            }
          });
          addToast?.(
            status.message || 'O motor local falhou repetidamente. Verifique os logs ou reinicie o aplicativo.',
            'error',
            10000
          );
        }
      });
    }

    return () => {
      if (unsubNotify) unsubNotify();
      if (unsubNavigate) unsubNavigate();
      if (unsubCancel) unsubCancel();
      if (unsubSymbols) unsubSymbols();
      if (unsubRecent) unsubRecent();
      if (unsubCloseAction) unsubCloseAction();
      if (unsubOllamaStopped) unsubOllamaStopped();
      if (unsubSidecarStatus) unsubSidecarStatus();
    };
  }, [setActiveTab, setSelectedFolder, setIsDevUnlocked, addToast]);

  // Sync recent chapters to Jump List & System Tray
  useEffect(() => {
    if (selectedFolder?.path && window.electronAPI?.addRecentChapter) {
      window.electronAPI.addRecentChapter(selectedFolder.path, selectedFolder.name);
    }
  }, [selectedFolder?.path, selectedFolder?.name]);
}
