import { create } from 'zustand';
import {
  createNavigationSlice,
  createChapterSlice,
  createJobSlice,
  createSettingsSlice,
  createRevisionSlice,
  DEFAULT_APP_SETTINGS,
} from './slices';

// Re-exportações canônicas para compatibilidade retroativa absoluta
export {
  createNavigationSlice,
  createChapterSlice,
  createJobSlice,
  createSettingsSlice,
  createRevisionSlice,
  DEFAULT_APP_SETTINGS,
};

// ── Store Central Unificado ──
export const useWorkspaceStore = create((...a) => ({
  ...createNavigationSlice(...a),
  ...createChapterSlice(...a),
  ...createJobSlice(...a),
  ...createSettingsSlice(...a),
  ...createRevisionSlice(...a),
}));

// Exposição global para o backend Python e integração contínua do Electron Shell
if (typeof window !== 'undefined') {
  window.workspaceStore = useWorkspaceStore;

  let prevRunningCount = 0;
  let prevProgress = -1;
  let prevStatusLabel = '';
  let prevChapterPath = null;
  let errorTimer = null;
  let successBadgeTimer = null;

  useWorkspaceStore.subscribe((state) => {
    if (!window.electronAPI) return;

    const queue = state.jobQueue || [];
    const runningJobs = queue.filter(j => j.status === 'running' || j.status === 'pending');
    const runningCount = runningJobs.length;
    const chapterChanged = state.activeChapterPath !== prevChapterPath;
    if (chapterChanged) {
      prevChapterPath = state.activeChapterPath;
    }

    // 1. Power Save Blocker: previne suspensão do Windows e economia de GPU enquanto houver lotes rodando
    if (runningCount > 0 && prevRunningCount === 0) {
      window.electronAPI.setActiveWork?.(true);
    } else if (runningCount === 0 && prevRunningCount > 0) {
      window.electronAPI.setActiveWork?.(false);
    }

    // 2. Barra de Tarefas do Windows (Taskbar Progress) e Bandeja do Sistema (Tray Menu)
    if (runningCount > 0) {
      if (errorTimer) {
        clearTimeout(errorTimer);
        errorTimer = null;
      }
      if (successBadgeTimer) {
        clearTimeout(successBadgeTimer);
        successBadgeTimer = null;
      }

      const totalProgress = runningJobs.reduce((acc, j) => acc + (j.progress || 0), 0);
      const avgProgress = Math.round(totalProgress / runningCount);
      const activeJob = runningJobs.find(j => j.status === 'running') || runningJobs[0];
      const progressFraction = Math.max(0.01, Math.min(1.0, (avgProgress || 5) / 100));

      if (avgProgress !== prevProgress) {
        prevProgress = avgProgress;
        window.electronAPI.setProgressBar?.(progressFraction, { mode: 'normal' });
      }

      const stepLabel = activeJob?.currentStepLabel || 'Processando lote';
      const trayStatus = `${stepLabel} (${avgProgress}% - ${runningCount} ${runningCount === 1 ? 'tarefa' : 'tarefas'})`;
      if (trayStatus !== prevStatusLabel || chapterChanged) {
        prevStatusLabel = trayStatus;
        window.electronAPI.updateTrayStatus?.(trayStatus, true, {
          badgeState: 'working',
          activeChapterName: state.activeChapterName || null,
          activeChapterPath: state.activeChapterPath || null,
          progressPercent: avgProgress,
          runningCount,
        });
      }
    } else {
      prevProgress = -1;
      if (prevRunningCount > 0) {
        const hasFailed = queue.some(j => j.status === 'failed');
        const hasCancelled = queue.some(j => j.status === 'cancelled');
        if (hasFailed) {
          window.electronAPI.setProgressBar?.(1, { mode: 'error' });
          if (errorTimer) clearTimeout(errorTimer);
          errorTimer = setTimeout(() => {
            window.electronAPI?.setProgressBar?.(-1, { mode: 'none' });
            errorTimer = null;
          }, 4000);
          prevStatusLabel = 'Finalizado com alertas';
          window.electronAPI.updateTrayStatus?.('Finalizado com alertas', false, {
            badgeState: 'error',
            activeChapterName: state.activeChapterName || null,
            activeChapterPath: state.activeChapterPath || null,
            progressPercent: null,
            runningCount: 0,
          });
        } else if (hasCancelled) {
          window.electronAPI.setProgressBar?.(-1, { mode: 'none' });
          prevStatusLabel = 'Cancelado pelo usuário';
          window.electronAPI.updateTrayStatus?.('Cancelado pelo usuário', false, {
            badgeState: 'idle',
            activeChapterName: state.activeChapterName || null,
            activeChapterPath: state.activeChapterPath || null,
            progressPercent: null,
            runningCount: 0,
          });
        } else {
          window.electronAPI.setProgressBar?.(-1, { mode: 'none' });
          prevStatusLabel = 'Lote concluído';
          window.electronAPI.updateTrayStatus?.('Lote concluído', false, {
            badgeState: 'success',
            activeChapterName: state.activeChapterName || null,
            activeChapterPath: state.activeChapterPath || null,
            progressPercent: 100,
            runningCount: 0,
          });
          if (successBadgeTimer) clearTimeout(successBadgeTimer);
          successBadgeTimer = setTimeout(() => {
            const currentStore = useWorkspaceStore.getState();
            const stillIdle = !(currentStore.jobQueue || []).some(j => j.status === 'running' || j.status === 'pending');
            if (stillIdle) {
              prevStatusLabel = 'Ocioso';
              window.electronAPI?.updateTrayStatus?.('Ocioso', false, {
                badgeState: 'idle',
                activeChapterName: currentStore.activeChapterName || null,
                activeChapterPath: currentStore.activeChapterPath || null,
              });
            }
            successBadgeTimer = null;
          }, 8000);
        }
      } else if (chapterChanged) {
        window.electronAPI.updateTrayStatus?.(prevStatusLabel || 'Ocioso', false, {
          badgeState: 'idle',
          activeChapterName: state.activeChapterName || null,
          activeChapterPath: state.activeChapterPath || null,
        });
      }
    }

    prevRunningCount = runningCount;
  });
}

export default useWorkspaceStore;
