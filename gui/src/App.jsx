import { useState, useEffect, memo, lazy, Suspense } from 'react';
import { useWorkspaceStore } from './stores/useWorkspaceStore';
import { useToast } from './contexts/ToastContext';
import { clientApi, eventBus } from './api/bridge';
import { safeSetStorageItem } from './utils/storage';

// Hooks extraídos
import { useExplorer } from './hooks/useExplorer';
import { useAppTheme } from './hooks/useAppTheme';
import { useDevMode } from './hooks/useDevMode';
import { useSidebar } from './hooks/useSidebar';
import { useWindowControls } from './hooks/useWindowControls';
import { useAppEvents } from './hooks/useAppEvents';

// Componentes extraídos
import { Titlebar } from './components/App/Titlebar';
import { AppTabs } from './components/App/AppTabs';
import { DevModeOverlay } from './components/App/DevModeOverlay';
import { ExplorerSidebar } from './components/App/ExplorerSidebar';

// Tela principal (imediata no boot)
import StudioWorkspace from './components/StudioWorkspace';
import QuickSymbolBar from './components/QuickSymbolBar';
import { ErrorBoundary } from './components/ErrorBoundary';

// Abas e overlays secundários carregados sob demanda (reduz bundle e parse no boot)
const loadLibrary = () => import('./components/Library');
const loadModulesCenter = () => import('./components/ModulesCenter');
const loadSettings = () => import('./components/Settings');
const loadDevDashboard = () => import('./components/DevDashboard');
const loadLightbox = () => import('./components/Lightbox');

const SECONDARY_TAB_LOADERS = {
  biblioteca: loadLibrary,
  lightbox: loadLightbox,
  modulos: loadModulesCenter,
  configuracoes: loadSettings,
};

const Library = lazy(loadLibrary);
const ModulesCenter = lazy(loadModulesCenter);
const Settings = lazy(loadSettings);
const DevDashboard = lazy(loadDevDashboard);
const Lightbox = lazy(loadLightbox);
const OnboardingModal = lazy(() => import('./components/OnboardingModal'));
const HelpInspectorOverlay = lazy(() =>
  import('./components/App/HelpInspectorOverlay').then((m) => ({ default: m.HelpInspectorOverlay }))
);

function TabLoadingFallback() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.6 }}>
      <div className="spinner-border" style={{ width: 22, height: 22 }} />
    </div>
  );
}

import './App.css';

// Componentes principais protegidos contra re-renders desnecessários do App
const MemoStudioWorkspace = memo(StudioWorkspace);
const MemoLibrary = memo(Library);
const MemoModulesCenter = memo(ModulesCenter);
const MemoSettings = memo(Settings);
const MemoDevDashboard = memo(DevDashboard);
const MemoLightbox = memo(Lightbox);

function App() {
  const activeTab = useWorkspaceStore((s) => s.activeTab);
  const setActiveTab = useWorkspaceStore((s) => s.setActiveTab);
  const { addToast } = useToast();
  
  const isOnboardingOpen = useWorkspaceStore((s) => s.isOnboardingOpen);
  const onboardingConfig = useWorkspaceStore((s) => s.onboardingConfig);
  const openOnboarding = useWorkspaceStore((s) => s.openOnboarding);
  const closeOnboarding = useWorkspaceStore((s) => s.closeOnboarding);
  const appSettings = useWorkspaceStore((s) => s.appSettings);
  const settingsRevision = useWorkspaceStore((s) => s.settingsRevision);

  const showPagePills = appSettings?.showPagePills !== false;
  const showStatusDots = appSettings?.showStatusDots !== false;
  const [backgroundDownload, setBackgroundDownload] = useState(null);
  const [isHelpInspectorActive, setIsHelpInspectorActive] = useState(false);
  // Mount-on-first-visit: mantém apenas o Estúdio imediato no boot e monta demais abas sob demanda,
  // preservando troca em 0ms após a primeira visita.
  const [visitedTabs, setVisitedTabs] = useState(() => ({
    processamento: true,
    [activeTab]: true,
  }));

  useEffect(() => {
    setVisitedTabs((prev) => (prev[activeTab] ? prev : { ...prev, [activeTab]: true }));
  }, [activeTab]);

  const isTabMounted = (tabId) => activeTab === tabId || Boolean(visitedTabs[tabId]);

  const prefetchTab = (tabId) => {
    const loader = SECONDARY_TAB_LOADERS[tabId];
    if (loader) {
      loader().catch(() => {});
    }
  };

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'F1') {
        e.preventDefault();
        setIsHelpInspectorActive((prev) => !prev);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Lógicas divididas
  const { applySettings, applyDevTheme, restoreUserTheme } = useAppTheme();
  const { isMaximized, handleToggleMaximize } = useWindowControls();
  const { isSidebarOpen, setIsSidebarOpen, sidebarWidth, isResizing, startResize } = useSidebar();
  const explorer = useExplorer();
  const devMode = useDevMode(applyDevTheme, restoreUserTheme, setActiveTab);

  // Escuta os eventos globais de notificação e jump list
  useAppEvents(
    setActiveTab, 
    explorer.setSelectedFolder, 
    devMode.setIsDevUnlocked, 
    explorer.selectedFolder, 
    addToast
  );

  // Inicialização limpa sem bloquear splash em decodificação de imagem, drives ou warmups concorrentes
  useEffect(() => {
    let notified = false;
    let disposed = false;
    let raf1 = null;
    let fallbackTimer = null;
    let warmupTimer = null;
    let ollamaTimer = null;
    const prewarmTimers = [];

    const scheduleIdlePrewarm = () => {
      const tabOrder = ['biblioteca', 'lightbox', 'modulos', 'configuracoes'];
      const enqueueNext = (idx) => {
        if (disposed || idx >= tabOrder.length) return;
        const tabId = tabOrder[idx];
        const loader = SECONDARY_TAB_LOADERS[tabId];
        const runStep = () => {
          if (disposed) return;
          Promise.resolve(loader ? loader() : null)
            .catch(() => {})
            .finally(() => {
              if (disposed) return;
              setVisitedTabs((prev) => (prev[tabId] ? prev : { ...prev, [tabId]: true }));
              const nextTimer = setTimeout(() => enqueueNext(idx + 1), 300);
              prewarmTimers.push(nextTimer);
            });
        };

        if (typeof window.requestIdleCallback === 'function') {
          window.requestIdleCallback(runStep, { timeout: 1500 });
        } else {
          const t = setTimeout(runStep, 120);
          prewarmTimers.push(t);
        }
      };

      // Inicia o pré-aquecimento ocioso das abas secundárias após boot/Ollama estabilizarem
      const startTimer = setTimeout(() => enqueueNext(0), 2800);
      prewarmTimers.push(startTimer);
    };

    const schedulePostBootTasks = () => {
      // Warmup em segundo plano só roda após o Estúdio estar aberto (zero disputa por disco/GIL no boot)
      warmupTimer = setTimeout(() => {
        Promise.allSettled([
          clientApi.checkModulesStatus().then((modStatus) => {
            if (modStatus) {
              safeSetStorageItem("visionary:cached_module_status", JSON.stringify({
                ocr: modStatus.ocr || { state: "not_installed" },
                cuda: modStatus.cuda || { state: "not_installed" },
                ollama: { state: "verifying" },
              }));
              if (Array.isArray(modStatus.ollamaModels)) {
                safeSetStorageItem("visionary:cached_ollama_models", JSON.stringify(modStatus.ollamaModels));
              }
              if (modStatus.ollamaModelsDetails) {
                safeSetStorageItem("visionary:cached_ollama_models_details", JSON.stringify(modStatus.ollamaModelsDetails));
              }
            }
          }),
          clientApi.getHardwareStats().then((hwStats) => {
            if (hwStats) {
              safeSetStorageItem("visionary:cached_hardware_stats", JSON.stringify(hwStats));
            }
          }),
        ]).catch(() => {});
      }, 1500);

      ollamaTimer = setTimeout(() => {
        clientApi.ensureOllamaRunning().catch(() => {});
      }, 2200);

      scheduleIdlePrewarm();
    };

    const signalReady = () => {
      if (notified) return;
      notified = true;
      if (fallbackTimer) clearTimeout(fallbackTimer);
      schedulePostBootTasks();
      raf1 = requestAnimationFrame(() => {
        if (typeof window.dismissVisionarySplash === 'function') {
          window.dismissVisionarySplash();
        }
        window.dispatchEvent(new CustomEvent('visionary:app-ready'));
        if (window.electronAPI?.notifyAppReady) {
          window.electronAPI.notifyAppReady();
        }
      });
    };

    // Safety timeout: se o backend travar ou falhar, a tela principal abre no máximo após 10000ms
    fallbackTimer = setTimeout(signalReady, 10000);

    const initApp = async () => {
      try {
        let settings = null;
        for (let attempt = 0; attempt < 35; attempt++) {
          try {
            settings = await clientApi.getSettings();
            if (settings) break;
          } catch (_) {
            const retryMs = attempt < 20 ? 60 : 200;
            await new Promise((r) => setTimeout(r, retryMs));
          }
        }
        if (settings) {
          applySettings(settings);
          useWorkspaceStore.getState().updateAppSettings(settings);
          if (settings.first_run_completed === false) {
            openOnboarding({ view: 'selection' });
          }
          window.electronAPI?.sendBootstrapProgress?.({
            percent: 75,
            mode: 'normal',
            message: 'Carregando preferências e espaço de trabalho...',
          });
        }

        const base = settings?.baseFolder;
        if (settings?.last_opened_folder) {
          const path = settings.last_opened_folder;
          const name = path.split(/[/\\]/).pop();
          if (explorer.selectedFolder?.path !== path) {
            explorer.setSelectedFolder({ path, name });
          }
          const parent = path.substring(0, Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/')));
          // Sidebar e listagem carregam em paralelo sem bloquear a revelação do Estúdio
          if (parent) {
            explorer.navigateTo(parent).catch(() => {});
          } else {
            explorer.loadDrives().catch(() => {});
          }
        } else if (base && base.trim()) {
          explorer.navigateTo(base.trim()).catch(() => {});
        } else {
          explorer.loadDrives().catch(() => {});
        }

        window.electronAPI?.sendBootstrapProgress?.({
          percent: 100,
          mode: 'normal',
          message: 'Pronto!',
        });
      } catch {
        explorer.loadDrives().catch(() => {});
      } finally {
        signalReady();
      }
    };

    initApp();

    return () => {
      disposed = true;
      notified = true;
      if (fallbackTimer) clearTimeout(fallbackTimer);
      if (warmupTimer) clearTimeout(warmupTimer);
      if (ollamaTimer) clearTimeout(ollamaTimer);
      prewarmTimers.forEach((t) => clearTimeout(t));
      if (raf1) cancelAnimationFrame(raf1);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applySettings, explorer.loadDrives, explorer.navigateTo, explorer.selectedFolder?.path, explorer.setSelectedFolder, openOnboarding]);

  // Sincronização em Tempo Real com Alterações de Configurações via Zustand
  useEffect(() => {
    if (appSettings) {
      applySettings(appSettings);
    }
  }, [appSettings, settingsRevision, applySettings]);

  // Mantém a pílula de download em segundo plano atualizando na Titlebar mesmo com o OnboardingModal fechado
  useEffect(() => {
    if (!backgroundDownload || isOnboardingOpen || backgroundDownload.progress >= 100) return;

    const isElite = backgroundDownload.profile === 'elite';
    const ollamaModelName = backgroundDownload.model || (isElite ? 'amadeus:32b' : 'amadeus:7b');
    const hfModelKey = isElite ? 'florence2_large' : 'florence2';

    const applyProgress = (res) => {
      if (!res || !res.success) return;
      const ollamaDl = res.ollama?.[ollamaModelName];
      const hfDl = res.hf?.[hfModelKey];
      const yoloDl = res.hf?.['yolo_detector'];

      const yoloDone = (yoloDl?.progress >= 100) || ['installed', 'ready', 'completed'].includes(yoloDl?.status);
      const florenceDone = (hfDl?.progress >= 100) || ['installed', 'ready', 'completed'].includes(hfDl?.status);
      const ollamaDone = (ollamaDl?.progress >= 100) || ['success', 'installed'].includes(ollamaDl?.status);

      const yoloPct = yoloDone ? 100 : (typeof yoloDl?.progress === 'number' ? yoloDl.progress : 0);
      const hfPct = florenceDone ? 100 : (typeof hfDl?.progress === 'number' ? hfDl.progress : 0);
      const ollamaPct = ollamaDone ? 100 : (typeof ollamaDl?.progress === 'number' ? ollamaDl.progress : 0);

      const isDone = ollamaDone && florenceDone && yoloDone;
      const calcOverall = Math.round((yoloPct * 0.05) + (hfPct * 0.15) + (ollamaPct * 0.80));

      setBackgroundDownload(prev => {
        if (!prev) return null;
        const overallPct = isDone ? 100 : Math.max(prev.progress || 0, calcOverall);
        return {
          ...prev,
          progress: overallPct,
          speedMb: ollamaDl?.speed_mbps || 0,
          text: isDone ? 'Modelos prontos' : `Baixando IA (${overallPct}%)`
        };
      });
    };

    const timer = setInterval(async () => {
      if (eventBus.isConnected()) return;
      try {
        const res = await clientApi.getDownloadsProgress();
        applyProgress(res);
      } catch (_) {}
    }, 1200);

    const unsub = eventBus.subscribe((payload) => {
      if (payload?.type === 'custom_event' && payload.event_name === 'downloads_progress' && payload.payload) {
        applyProgress(payload.payload);
      }
    });

    return () => {
      clearInterval(timer);
      unsub();
    };
  }, [backgroundDownload, isOnboardingOpen]);

  const handleEntryClick = (entry) => {
    if (entry.isBack) {
      explorer.navigateTo(entry.targetPath);
    } else if (entry.isDir || entry.isDrive) {
      if (entry.hasImages) {
        explorer.setSelectedFolder({ path: entry.path, name: entry.name });
        if (activeTab !== 'processamento' && activeTab !== 'lightbox') {
          setActiveTab('processamento');
        }
      } else {
        explorer.navigateTo(entry.path);
      }
    }
  };

  return (
    <div className="app-container">
      <Titlebar 
        isDevUnlocked={devMode.isDevUnlocked}
        devUser={devMode.devUser}
        selectedFolder={explorer.selectedFolder}
        isMaximized={isMaximized}
        handleToggleMaximize={handleToggleMaximize}
        handleSecretClick={devMode.handleSecretClick}
        backgroundDownload={backgroundDownload}
        onOpenOnboarding={() => {
          openOnboarding({
            view: backgroundDownload ? 'downloading' : 'selection',
            isDebugPreview: false
          });
        }}
      />

      <div className="app-body">
        <ExplorerSidebar 
          activeTab={activeTab}
          isSidebarOpen={isSidebarOpen}
          setIsSidebarOpen={setIsSidebarOpen}
          sidebarWidth={sidebarWidth}
          isResizing={isResizing}
          startResize={startResize}
          handleSecretClick={devMode.handleSecretClick}
          handleGoUp={explorer.handleGoUp}
          isAtRoot={explorer.isAtRoot}
          currentPath={explorer.currentPath}
          refreshCurrentDirectory={explorer.refreshCurrentDirectory}
          searchQuery={explorer.searchQuery}
          setSearchQuery={explorer.setSearchQuery}
          filteredEntries={explorer.filteredEntries}
          handleEntryClick={handleEntryClick}
          selectedFolder={explorer.selectedFolder}
          showStatusDots={showStatusDots}
          showPagePills={showPagePills}
        />

        <main className="app-main">
          <AppTabs 
            activeTab={activeTab}
            handleTabChange={setActiveTab}
            onPrefetchTab={prefetchTab}
            isSidebarOpen={isSidebarOpen}
            setIsSidebarOpen={setIsSidebarOpen}
            selectedFolder={explorer.selectedFolder}
            isDevUnlocked={devMode.isDevUnlocked}
            isHelpInspectorActive={isHelpInspectorActive}
            onToggleHelpInspector={() => setIsHelpInspectorActive((prev) => !prev)}
          />
          
          <div className="tab-content">
            <ErrorBoundary>
              <div 
                className={`tab-pane ${activeTab === 'processamento' ? 'active' : ''}`} 
                style={{ display: activeTab === 'processamento' ? 'block' : 'none', height: '100%', width: '100%' }}
              >
                <MemoStudioWorkspace folderPath={explorer.selectedFolder?.path} folderName={explorer.selectedFolder?.name} isActive={activeTab === 'processamento'} />
              </div>
              {isTabMounted('biblioteca') && (
                <div 
                  className={`tab-pane ${activeTab === 'biblioteca' ? 'active' : ''}`} 
                  style={{ display: activeTab === 'biblioteca' ? 'block' : 'none', height: '100%', width: '100%' }}
                >
                  <Suspense fallback={<TabLoadingFallback />}>
                    <MemoLibrary activeChapterName={explorer.selectedFolder?.name} activeChapterPath={explorer.selectedFolder?.path} isActive={activeTab === 'biblioteca'} />
                  </Suspense>
                </div>
              )}
              {isTabMounted('lightbox') && (
                <div 
                  className={`tab-pane ${activeTab === 'lightbox' ? 'active' : ''}`} 
                  style={{ display: activeTab === 'lightbox' ? 'block' : 'none', height: '100%', width: '100%' }}
                >
                  <Suspense fallback={<TabLoadingFallback />}>
                    <MemoLightbox activeChapterPath={explorer.selectedFolder?.path} isActive={activeTab === 'lightbox'} />
                  </Suspense>
                </div>
              )}
              {isTabMounted('modulos') && (
                <div 
                  className={`tab-pane ${activeTab === 'modulos' ? 'active' : ''}`} 
                  style={{ display: activeTab === 'modulos' ? 'block' : 'none', height: '100%', width: '100%' }}
                >
                  <Suspense fallback={<TabLoadingFallback />}>
                    <MemoModulesCenter isActive={activeTab === 'modulos'} />
                  </Suspense>
                </div>
              )}
              {isTabMounted('configuracoes') && (
                <div 
                  className={`tab-pane ${activeTab === 'configuracoes' ? 'active' : ''}`} 
                  style={{ display: activeTab === 'configuracoes' ? 'block' : 'none', height: '100%', width: '100%' }}
                >
                  <Suspense fallback={<TabLoadingFallback />}>
                    <MemoSettings onBaseFolderChange={(val) => (val ? explorer.navigateTo(val) : explorer.loadDrives())} />
                  </Suspense>
                </div>
              )}
              {devMode.isDevUnlocked && (
                <div 
                  className={`tab-pane ${activeTab === 'testes' ? 'active' : ''}`} 
                  style={{ display: activeTab === 'testes' ? 'flex' : 'none', height: '100%', width: '100%', flexDirection: 'column', position: 'relative' }}
                >
                  <Suspense fallback={null}>
                    <MemoDevDashboard isActive={activeTab === 'testes'} />
                  </Suspense>
                </div>
              )}
            </ErrorBoundary>
          </div>
        </main>
      </div>

      <DevModeOverlay 
        devTransition={devMode.devTransition}
        devLoadingFading={devMode.devLoadingFading}
        skipDevLoading={devMode.skipDevLoading}
        devLoadingProgress={devMode.devLoadingProgress}
        devUser={devMode.devUser}
        devLogIndex={devMode.devLogIndex}
        showPasswordModal={devMode.showPasswordModal}
        setShowPasswordModal={devMode.setShowPasswordModal}
        handlePasswordSubmit={devMode.handlePasswordSubmit}
        passwordInput={devMode.passwordInput}
        setPasswordInput={devMode.setPasswordInput}
        passwordError={devMode.passwordError}
        setPasswordError={devMode.setPasswordError}
      />

      <QuickSymbolBar />

      {isHelpInspectorActive && (
        <Suspense fallback={null}>
          <HelpInspectorOverlay
            isActive={isHelpInspectorActive}
            onClose={() => setIsHelpInspectorActive(false)}
            onOpenFullDocs={null}
            onSwitchTab={(tab) => setActiveTab(tab)}
          />
        </Suspense>
      )}

      {isOnboardingOpen && (
        <Suspense fallback={null}>
          <OnboardingModal 
            isOpen={isOnboardingOpen}
            initialView={onboardingConfig?.view || 'selection'}
            isDebugPreview={Boolean(onboardingConfig?.isDebugPreview)}
            onClose={closeOnboarding}
            onStartBackground={(dlInfo) => {
              setBackgroundDownload(dlInfo);
            }}
          />
        </Suspense>
      )}
    </div>
  );
}

export default App;
