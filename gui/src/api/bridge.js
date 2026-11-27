// Cliente de API do frontend: roteia chamadas entre IPC do Electron, FastAPI (/api/rpc) e WebSocket (/ws/logs).

const DEFAULT_SERVER_URL = "http://127.0.0.1:5000";

export function resolveInitialServerUrl(searchStr = typeof window !== "undefined" ? window.location?.search : "") {
  try {
    if (searchStr) {
      const paramUrl = new URLSearchParams(searchStr).get("serverUrl");
      if (paramUrl && /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/?$/i.test(paramUrl.trim())) {
        return paramUrl.trim().replace(/\/+$/, "");
      }
    }
  } catch (_) {}
  return DEFAULT_SERVER_URL;
}

let serverBaseUrl = resolveInitialServerUrl();
let eventBusInstance = null;

// Descoberta dinâmica da porta do backend FastAPI (pode mudar se a 5000 estiver ocupada)
export function setServerUrl(url) {
  const cleanUrl = String(url || "").replace(/\/+$/, "");
  if (!cleanUrl) return;
  const changed = serverBaseUrl !== cleanUrl;
  serverBaseUrl = cleanUrl;
  if (changed && eventBusInstance) {
    eventBusInstance.handleServerUrlChanged();
  }
}

if (typeof window !== "undefined" && window.electronAPI && typeof window.electronAPI.getServerUrl === "function") {
  window.electronAPI.getServerUrl().then((url) => {
    if (url) {
      setServerUrl(url);
    }
  }).catch(() => {});
}

/**
 * Retorna a URL base do servidor FastAPI síncrona (geralmente http://127.0.0.1:5000).
 * @returns {string} A URL base sem barra no final.
 * @warning Sempre importe diretamente: `import { getServerUrl } from '../api/bridge'`.
 */
export function getServerUrl() {
  return serverBaseUrl;
}

// Despacha chamadas RPC genéricas para /api/rpc/{methodName}
export async function callRpc(methodName, ...args) {
  try {
    const response = await fetch(`${serverBaseUrl}/api/rpc/${methodName}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ args, kwargs: {} }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    if (data && data.success === false && data.error) {
      throw new Error(data.error);
    }
    return data.result;
  } catch (error) {
    console.error(`[Universal Bridge] Error calling ${methodName}:`, error);
    throw error;
  }
}

// Proxy dinâmico que prioriza handlers nativos do Electron (janela, diálogos, shell) e envia o restante via HTTP RPC
export const clientApi = new Proxy(
  {},
  {
    get(_target, prop) {
      if (typeof prop === "string") {
        // Permite que testes unitários injetem mocks em window.pywebview.api sem gerar recursão com o próprio proxy
        if (
          typeof window !== "undefined" &&
          window.pywebview?.api &&
          window.pywebview.api !== clientApi &&
          typeof window.pywebview.api[prop] === "function"
        ) {
          return (...args) => window.pywebview.api[prop](...args);
        }

        if (typeof window !== "undefined" && window.electronAPI) {
          if (prop === "minimize") return () => window.electronAPI.minimize();
          if (prop === "toggle_maximize") return () => window.electronAPI.toggleMaximize();
          if (prop === "get_is_maximized") return () => window.electronAPI.isMaximized();
          if (prop === "close") return () => window.electronAPI.close();
          if (prop === "restartSidecar") return () => window.electronAPI.restartSidecar?.();
          if (prop === "select_folder" || prop === "selectFolder") {
            return (defaultPath) => window.electronAPI.selectFolder(defaultPath);
          }
          if (prop === "openPath") {
            return (fullPath) => window.electronAPI.openPath(fullPath);
          }
          if (prop === "showItemInFolder") {
            return (fullPath) => window.electronAPI.showItemInFolder(fullPath);
          }
          if (prop === "openFileInExplorer") {
            return async (targetPath) => {
              if (window.electronAPI?.showItemInFolder) {
                const res = await window.electronAPI.showItemInFolder(targetPath);
                if (res && res.success !== false) return res;
              }
              return callRpc("openFileInExplorer", targetPath);
            };
          }
          if (prop === "openLibraryFolder") {
            return async (targetFolder) => {
              if (targetFolder && window.electronAPI?.openPath) {
                const res = await window.electronAPI.openPath(targetFolder);
                if (res && res.success !== false) return res;
              }
              const res = await callRpc("openLibraryFolder", targetFolder);
              if (res?.path && window.electronAPI?.openPath) {
                await window.electronAPI.openPath(res.path);
              }
              return res;
            };
          }
        }
        return (...args) => callRpc(prop, ...args);
      }
      return undefined;
    },
  }
);

// Assinatura em tempo real dos logs e eventos de progresso via WebSocket
export class ServerEventBus {
  constructor(heartbeatIntervalMs = 15000) {
    this.listeners = new Set();
    this.ws = null;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.heartbeatIntervalMs = heartbeatIntervalMs;
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === (typeof WebSocket !== "undefined" ? WebSocket.OPEN : 1)) {
        try {
          this.ws.send("ping");
        } catch (_) {
          this.cleanupSocket();
          this.reconnect();
        }
      }
    }, this.heartbeatIntervalMs);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  cleanupSocket() {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      try {
        const isOpenOrConnecting =
          typeof WebSocket !== "undefined"
            ? this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING
            : this.ws.readyState === 0 || this.ws.readyState === 1;
        if (isOpenOrConnecting) {
          this.ws.close();
        }
      } catch (_) {}
      this.ws = null;
    }
  }

  connect() {
    if (typeof WebSocket === "undefined") return;

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.cleanupSocket();

    const wsUrl = serverBaseUrl.replace(/^http/, "ws") + "/ws/logs";
    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        if (event.data === "pong") {
          return;
        }
        try {
          const payload = JSON.parse(event.data);
          this.listeners.forEach((callback) => {
            try {
              callback(payload);
            } catch (err) {
              console.error("[ServerEventBus] Listener error:", err);
            }
          });
        } catch (_) {}
      };

      this.ws.onclose = () => {
        this.cleanupSocket();
        this.reconnect();
      };

      this.ws.onerror = () => {
        this.cleanupSocket();
        this.reconnect();
      };
    } catch (_) {
      this.cleanupSocket();
      this.reconnect();
    }
  }

  reconnect() {
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connect(), 2000);
  }

  isConnected() {
    return typeof WebSocket !== "undefined" && this.ws?.readyState === WebSocket.OPEN;
  }

  subscribe(callback) {
    this.listeners.add(callback);
    if (!this.isConnected()) {
      this.connect();
    }
    return () => {
      this.listeners.delete(callback);
    };
  }

  handleServerUrlChanged() {
    clearTimeout(this.reconnectTimer);
    if (this.listeners.size > 0 || this.ws) {
      this.cleanupSocket();
      this.connect();
    }
  }
}

export const eventBus = new ServerEventBus();
eventBusInstance = eventBus;

if (typeof window !== "undefined" && window.addEventListener) {
  window.addEventListener("online", () => {
    if (!eventBus.isConnected()) {
      eventBus.connect();
    }
  });
}

// Throttled UI updater para logs e progresso de alta frequência (buffer suave de ~80ms / rAF)
export class ThrottledUiQueue {
  constructor(throttleMs = 80) {
    this.logBuffers = new Map(); // jobId -> Array<string>
    this.progressBuffer = new Map(); // jobId -> { progress, step_label }
    this.timer = null;
    this.rafId = null;
    this.throttleMs = throttleMs;
    this.lastFlush = 0;
  }

  enqueueLogs(jobId, logs) {
    if (!jobId || !logs) return;
    if (!this.logBuffers.has(jobId)) {
      this.logBuffers.set(jobId, []);
    }
    const buf = this.logBuffers.get(jobId);
    if (Array.isArray(logs)) {
      for (let i = 0; i < logs.length; i++) {
        if (logs[i]) buf.push(logs[i]);
      }
    } else {
      buf.push(logs);
    }
    this.scheduleFlush();
  }

  enqueueProgress(jobId, progress, stepLabel) {
    if (!jobId) return;
    const current = this.progressBuffer.get(jobId) || {};
    if (progress !== undefined && progress >= 0) current.progress = progress;
    if (stepLabel) current.currentStepLabel = stepLabel;
    this.progressBuffer.set(jobId, current);

    // Se o progresso bateu 100%, faz flush imediato para conclusão visual instantânea
    if (progress === 100) {
      this.flushNow();
      return;
    }
    this.scheduleFlush();
  }

  scheduleFlush() {
    if (this.timer !== null || this.rafId !== null) return;
    const now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    const elapsed = now - this.lastFlush;

    const runFlush = () => {
      this.timer = null;
      this.rafId = null;
      this.flushNow();
    };

    if (elapsed >= this.throttleMs) {
      if (typeof requestAnimationFrame !== 'undefined') {
        this.rafId = requestAnimationFrame(runFlush);
      } else {
        this.timer = setTimeout(runFlush, 0);
      }
    } else {
      const wait = this.throttleMs - elapsed;
      this.timer = setTimeout(() => {
        this.timer = null;
        if (typeof requestAnimationFrame !== 'undefined') {
          this.rafId = requestAnimationFrame(runFlush);
        } else {
          runFlush();
        }
      }, wait);
    }
  }

  flushNow() {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.rafId !== null) {
      if (typeof cancelAnimationFrame !== 'undefined') {
        cancelAnimationFrame(this.rafId);
      }
      this.rafId = null;
    }
    this.lastFlush = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();

    const store = window.workspaceStore ? window.workspaceStore.getState() : null;
    if (!store) return;

    // 1. Flush de logs acumulados em bloco atômico no Zustand
    if (this.logBuffers.size > 0) {
      for (const [jobId, lines] of this.logBuffers.entries()) {
        if (lines && lines.length > 0) {
          if (store.appendJobLogs) {
            store.appendJobLogs(jobId, lines);
          } else {
            lines.forEach(l => store.appendJobLog(jobId, l));
          }
        }
      }
      this.logBuffers.clear();
    }

    // 2. Flush de progressos consolidados
    if (this.progressBuffer.size > 0) {
      for (const [jobId, updates] of this.progressBuffer.entries()) {
        store.updateJob(jobId, updates);
      }
      this.progressBuffer.clear();
    }
  }
}

export const throttledUi = new ThrottledUiQueue();

// Auto-install polyfill onto window.pywebview.api for 100% backward compatibility
export function installUniversalBridge() {
  window.pywebview = window.pywebview || {};
  window.pywebview.api = clientApi;
  
  eventBus.subscribe((payload) => {
    if (!payload || !payload.type) return;
    const store = window.workspaceStore ? window.workspaceStore.getState() : null;

    const jid = payload.job_id || payload.extra?.job_id;
    if (payload.type === 'job_progress') {
      if (jid) {
        throttledUi.enqueueProgress(jid, payload.progress, payload.step_label || payload.extra?.step_label);
      }
    } else if (payload.type === 'job_log') {
      if (jid) {
        const rawLogs = payload.logs || payload.extra?.logs;
        const lines = Array.isArray(rawLogs) ? rawLogs : (payload.message ? [payload.message] : null);
        if (lines) {
          throttledUi.enqueueLogs(jid, lines);
        }
      }
    } else if (payload.type === 'pipeline_status' || payload.type === 'pipeline_error') {
      if (store && payload.message) {
        const activeJob = (jid ? store.jobQueue.find(j => j.id === jid) : null) || store.jobQueue.find(j => j.status === 'running') || store.jobQueue[0];
        if (activeJob) {
          throttledUi.enqueueLogs(activeJob.id, [payload.message]);
          if (payload.progress !== undefined && payload.progress >= 0) {
            throttledUi.enqueueProgress(activeJob.id, payload.progress);
          }
        }
      }
    } else if (payload.type === 'job_status') {
      // Evento crítico de transição de status: descarrega logs e progresso pendentes imediatamente
      throttledUi.flushNow();
      const statusJid = payload.job_id || payload.extra?.job_id;
      const updates = payload.updates || payload.extra?.updates;
      if (store && statusJid && updates) {
        store.updateJob(statusJid, updates);
      }
    } else if (payload.type === 'custom_event') {
      if (payload.event_name === 'onOllamaReady') {
        if (store?.bumpOllamaRevision) {
          store.bumpOllamaRevision();
        }
      }
    }
  });

  if (typeof window !== "undefined" && window.electronAPI?.onSidecarStatus) {
    window.electronAPI.onSidecarStatus((status) => {
      if (!status || typeof status !== "object") return;
      if (status.state === "online") {
        if (status.serverUrl) {
          setServerUrl(status.serverUrl);
        }
        if (!eventBus.isConnected()) {
          eventBus.connect();
        }
      }
    });
  }

  eventBus.connect();
  console.log("[Universal Bridge] Polyfill active. Connected to:", serverBaseUrl);
}
