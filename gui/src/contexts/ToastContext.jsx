import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import '../components/Toast.css';
import { Check, X, Info, AlertTriangle } from 'lucide-react';

// oxlint-disable-next-line react/only-export-components
export const ToastContext = createContext(null);

// oxlint-disable-next-line react/only-export-components
export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

// Componente individual do Toast (para avisos e erros críticos persistentes)
const ToastItem = ({ toast, onDismiss, onRemove }) => {
  const [isPaused, setIsPaused] = useState(false);
  const [progress, setProgress] = useState(100);
  const timerRef = useRef(null);
  const startTimeRef = useRef(Date.now());
  const remainingTimeRef = useRef(toast.duration);
  const intervalRef = useRef(null);

  const pauseTimer = useCallback(() => {
    if (toast.duration <= 0 || toast.isExiting) return;
    const elapsed = Date.now() - startTimeRef.current;
    remainingTimeRef.current = Math.max(0, remainingTimeRef.current - elapsed);
    setIsPaused(true);
  }, [toast.duration, toast.isExiting]);

  const resumeTimer = useCallback(() => {
    if (toast.duration <= 0 || toast.isExiting) return;
    startTimeRef.current = Date.now();
    setIsPaused(false);
  }, [toast.duration, toast.isExiting]);

  useEffect(() => {
    if (toast.duration <= 0 || toast.isExiting || isPaused) {
      return;
    }

    startTimeRef.current = Date.now();

    timerRef.current = setTimeout(() => {
      onDismiss(toast.id);
    }, remainingTimeRef.current);

    intervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startTimeRef.current;
      const remaining = Math.max(0, remainingTimeRef.current - elapsed);
      const percentage = (remaining / toast.duration) * 100;
      setProgress(percentage);
    }, 50);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [toast.id, toast.duration, toast.isExiting, isPaused, onDismiss]);

  // Quando marcado para fechar (isExiting), aguarda o tempo da animação CSS antes de remover da DOM
  useEffect(() => {
    if (toast.isExiting) {
      const timeout = setTimeout(() => {
        onRemove(toast.id);
      }, 350); // tempo compatível com slideOut / fadeOut
      return () => clearTimeout(timeout);
    }
  }, [toast.isExiting, toast.id, onRemove]);

  return (
    <div 
      className={`toast toast-${toast.type} ${toast.isExiting ? 'toast-exit' : 'toast-enter'} ${isPaused ? 'toast-paused' : ''}`}
      onMouseEnter={pauseTimer}
      onMouseLeave={resumeTimer}
    >
      <div className="toast-icon-wrapper">
        <div className="toast-icon">
          {toast.type === 'success' && <Check size={14} />}
          {toast.type === 'error' && <X size={14} />}
          {toast.type === 'warning' && <AlertTriangle size={14} />}
          {toast.type === 'info' && <Info size={14} />}
        </div>
      </div>
      
      <div className="toast-content">
        <div className="toast-message">
          {toast.message}
          {toast.count > 1 && (
            <span className="toast-badge-count" title="Mensagens repetidas agrupadas">
              {toast.count}x
            </span>
          )}
        </div>
      </div>

      <button className="toast-close" onClick={() => onDismiss(toast.id)} aria-label="Fechar notificação">
        <X size={13} />
      </button>

      {toast.duration > 0 && (
        <div className="toast-progress">
          <div 
            className="toast-progress-bar" 
            style={{ 
              width: `${progress}%`,
              transition: isPaused ? 'none' : 'width 50ms linear'
            }} 
          />
        </div>
      )}
    </div>
  );
};

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);
  const [statusFlash, setStatusFlash] = useState(null);
  const flashTimerRef = useRef(null);
  const MAX_TOASTS = 3; // Limita a pilha para evitar poluição visual na interface

  const flashStatus = useCallback((message, type = 'info', duration = 2800) => {
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    const id = Date.now();
    setStatusFlash({ text: message, type, id });
    if (duration > 0) {
      flashTimerRef.current = setTimeout(() => {
        setStatusFlash((prev) => (prev?.id === id ? null : prev));
      }, duration);
    }
  }, []);

  const addToast = useCallback((message, type = 'success', duration = 4000, options = {}) => {
    let resolvedMessage = message;
    let resolvedType = type;
    let resolvedDuration = duration;

    // Normalização defensiva: se um objeto foi passado como primeiro parâmetro (ex: { type, message })
    if (typeof message === 'object' && message !== null) {
      resolvedMessage = message.message || message.text || '';
      resolvedType = message.type || type;
      resolvedDuration = message.duration || duration;
    }

    // 1. Notificações puramente informativas e de transição de tela acendem na Barra de Rodapé (Status Bar)
    if (resolvedType === 'info' && !options?.forceToast) {
      flashStatus(resolvedMessage, 'info', Math.min(resolvedDuration, 3000));
      return;
    }

    // 2. Erros, avisos e sucessos também atualizam o feedback na barra de status
    flashStatus(resolvedMessage, resolvedType, Math.min(resolvedDuration, 3500));

    setToasts((prev) => {
      // Desduplicação: Se o mesmo toast já existir ativo, apenas incrementamos o contador
      const existingIndex = prev.findIndex(t => t.message === resolvedMessage && t.type === resolvedType && !t.isExiting);
      if (existingIndex !== -1) {
        const updated = [...prev];
        updated[existingIndex] = {
          ...updated[existingIndex],
          count: (updated[existingIndex].count || 1) + 1,
          updatedAt: Date.now()
        };
        return updated;
      }

      // Criar novo toast
      const newToast = {
        id: Date.now() + Math.random().toString(36).substring(2, 9),
        message: resolvedMessage,
        type: resolvedType,
        duration: resolvedDuration,
        count: 1,
        isExiting: false,
        createdAt: Date.now()
      };

      // Controle de limite da pilha: se exceder MAX_TOASTS, marca o mais antigo para sair
      let newStack = [...prev, newToast];
      const activeToasts = newStack.filter(t => !t.isExiting);
      if (activeToasts.length > MAX_TOASTS) {
        const oldestActiveId = activeToasts[0].id;
        newStack = newStack.map(t => t.id === oldestActiveId ? { ...t, isExiting: true } : t);
      }

      return newStack;
    });
  }, [flashStatus]);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.map((toast) => toast.id === id ? { ...toast, isExiting: true } : toast));
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, statusFlash, flashStatus }}>
      {children}
      <div className="toast-viewport">
        <div className="toast-container">
          {toasts.map((toast) => (
            <ToastItem 
              key={toast.id} 
              toast={toast} 
              onDismiss={dismissToast} 
              onRemove={removeToast} 
            />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
};
