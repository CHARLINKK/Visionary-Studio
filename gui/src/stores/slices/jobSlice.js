import { clientApi } from '../../api/bridge';

/**
 * Slice 3: Fila de Tarefas em Lote (Job Queue)
 */
export const createJobSlice = (set, get) => ({
  jobQueue: [], // [{ id, type, status, progress, page }]

  addJob: (job) => set((state) => {
    const existingIndex = state.jobQueue.findIndex(j => j.id === job.id);
    if (existingIndex >= 0) {
      const existing = state.jobQueue[existingIndex];
      const merged = {
        ...existing,
        ...job,
        logs: (job.logs && job.logs.length >= (existing.logs || []).length) ? job.logs : (existing.logs || []),
        progress: Math.max(existing.progress || 0, job.progress || 0),
        currentStepLabel: existing.currentStepLabel || job.currentStepLabel || 'Iniciando...'
      };
      const newQueue = [...state.jobQueue];
      newQueue[existingIndex] = merged;
      return { jobQueue: newQueue };
    }
    return {
      jobQueue: [...state.jobQueue, { 
        ...job, 
        logs: job.logs || [], 
        showLogs: job.showLogs || false, 
        currentStepLabel: job.currentStepLabel || 'Iniciando...',
        startedAt: job.startedAt || Date.now()
      }]
    };
  }),

  updateJob: (jobId, updates) => set((state) => {
    const jobExists = state.jobQueue.some(j => j.id === jobId);
    if (!jobExists) return state;

    let hasChanged = false;
    const newQueue = state.jobQueue.map(j => {
      if (j.id !== jobId) return j;
      const newUpdates = { ...updates };
      if (updates.logs && Array.isArray(updates.logs)) {
        if (updates.logs.length >= (j.logs || []).length) {
          newUpdates.logs = updates.logs;
        }
      }
      if (updates.progress !== undefined) {
        const prevProg = j.progress || 0;
        const targetProg = Math.min(100, Math.max(0, Math.round(updates.progress)));
        newUpdates.progress = updates.progress === 0 ? 0 : Math.max(prevProg, targetProg);
      }
      if ((updates.status === 'completed' || updates.status === 'failed' || updates.status === 'cancelled') && !j.completedAt) {
        newUpdates.completedAt = Date.now();
        if (updates.status === 'completed') {
          newUpdates.progress = 100;
        }
      }

      let changed = false;
      for (const k in newUpdates) {
        if (j[k] !== newUpdates[k]) {
          changed = true;
          break;
        }
      }
      if (!changed) return j;
      hasChanged = true;
      return { ...j, ...newUpdates };
    });
    return hasChanged ? { jobQueue: newQueue } : state;
  }),

  updateJobProgress: (jobId, progress, label) => set((state) => {
    let hasChanged = false;
    const newQueue = state.jobQueue.map(j => {
      if (j.id !== jobId) return j;
      const prevProg = j.progress || 0;
      const targetProg = Math.min(100, Math.max(0, Math.round(progress)));
      const nextProg = Math.max(prevProg, targetProg);
      const nextLabel = label !== undefined ? label : j.currentStepLabel;
      if (j.progress === nextProg && j.currentStepLabel === nextLabel) return j;
      hasChanged = true;
      return { 
        ...j, 
        progress: nextProg, 
        currentStepLabel: nextLabel 
      };
    });
    return hasChanged ? { jobQueue: newQueue } : state;
  }),

  appendJobLogs: (jobId, newLogLines) => set((state) => {
    if (!newLogLines || newLogLines.length === 0) return state;
    const lines = (Array.isArray(newLogLines) ? newLogLines : [newLogLines]).filter(Boolean);
    if (lines.length === 0) return state;

    const jobExists = state.jobQueue.some(j => j.id === jobId);
    if (!jobExists) return state;

    let hasChanged = false;
    const newQueue = state.jobQueue.map(j => {
      if (j.id !== jobId) return j;
      let updatedLogs = j.logs ? [...j.logs] : [];

      for (const rawLine of lines) {
        if (!rawLine) continue;
        let line = rawLine;
        let isReplace = false;
        let replacePrefix = null;

        const replaceMatch = line.match(/\[REPLACE_LAST_LOG_PREFIX:(.+?)\]/);
        if (replaceMatch) {
          isReplace = true;
          replacePrefix = replaceMatch[1];
          line = line.replace(replaceMatch[0], "").trim();
        }

        if (isReplace) {
          let found = false;
          for (let i = updatedLogs.length - 1; i >= Math.max(0, updatedLogs.length - 30); i--) {
            if (updatedLogs[i].includes(replacePrefix)) {
              updatedLogs[i] = line;
              found = true;
              break;
            }
          }
          if (!found) {
            updatedLogs.push(line);
          }
        } else {
          updatedLogs.push(line);
        }
      }

      hasChanged = true;
      if (updatedLogs.length > 1500) {
        updatedLogs = updatedLogs.slice(updatedLogs.length - 1500);
      }
      return { ...j, logs: updatedLogs };
    });

    return hasChanged ? { jobQueue: newQueue } : state;
  }),

  appendJobLog: (jobId, logLine) => {
    if (logLine) {
      get().appendJobLogs(jobId, [logLine]);
    }
  },

  toggleJobLogs: (jobId) => set((state) => ({
    jobQueue: state.jobQueue.map(j => 
      j.id === jobId ? { ...j, showLogs: !j.showLogs } : j
    )
  })),

  cancelJob: (jobId, hardReset = false) => {
    clientApi.cancelJob(jobId, hardReset).catch(() => {});
    set((state) => ({
      jobQueue: state.jobQueue.map(j => 
        j.id === jobId 
          ? { 
              ...j, 
              status: 'cancelled', 
              currentStepLabel: 'Cancelado pelo usuário', 
              error: 'Interrompido manualmente.', 
              completedAt: Date.now() 
            } 
          : j
      )
    }));
  },

  cancelAllJobs: (hardReset = false) => {
    const { jobQueue } = get();
    const runningJobs = jobQueue.filter(j => j.status === 'running' || j.status === 'pending');
    const jobId = runningJobs[0]?.id || 'all';
    clientApi.cancelJob(jobId, hardReset).catch(() => {});
    set((state) => ({
      jobQueue: state.jobQueue.map(j => 
        (j.status === 'running' || j.status === 'pending')
          ? { 
              ...j, 
              status: 'cancelled', 
              currentStepLabel: 'Cancelado pelo usuário', 
              error: 'Interrompido manualmente via bandeja/menu.', 
              completedAt: Date.now() 
            } 
          : j
      )
    }));
  },

  removeJob: (jobId) => set((state) => ({
    jobQueue: state.jobQueue.filter(j => j.id !== jobId)
  })),

  clearCompletedJobs: () => {
    clientApi.clearCompletedJobs().catch(() => {});
    set((state) => ({
      jobQueue: state.jobQueue.filter(j => j.status !== 'completed' && j.status !== 'failed' && j.status !== 'cancelled')
    }));
  },

  clearJobLogs: (jobId) => {
    clientApi.clearJobLogs(jobId).catch(() => {});
    set((state) => ({
      jobQueue: state.jobQueue.map(j => j.id === jobId ? { ...j, logs: [] } : j)
    }));
  },
});
