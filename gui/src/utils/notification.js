import { playChime } from './sound';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { clientApi } from '../api/bridge';

export function isNotificationEnabled() {
  if (typeof window === 'undefined') return true;
  const stored = localStorage.getItem('visionary:system_notifications');
  if (stored !== null) return stored === 'true';
  return true;
}

export function setNotificationEnabled(enabled) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('visionary:system_notifications', enabled ? 'true' : 'false');
}

export function isNotifyOnlyInBackground() {
  if (typeof window === 'undefined') return true;
  const stored = localStorage.getItem('visionary:notify_only_background');
  if (stored !== null) return stored === 'true';
  return true;
}

export function setNotifyOnlyInBackground(enabled) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('visionary:notify_only_background', enabled ? 'true' : 'false');
}

/**
 * Emite uma notificação nativa para o Windows (Action Center / Toast).
 * Ao clicar na notificação, restaura e foca a janela do Visionary Studio,
 * e opcionalmente troca para a aba solicitada (ex: 'processamento', 'biblioteca').
 */
export async function sendNativeNotification(title, message, options = {}) {
  const { playSound = true, force = false, actionTab = null } = options;

  if (!force && !isNotificationEnabled()) return;

  // Notificações Inteligentes: se a janela estiver visível e em foco no SO, não incomoda com toast nativo
  if (!force && isNotifyOnlyInBackground()) {
    const isAppFocused = typeof document !== 'undefined' && document.hasFocus() && document.visibilityState === 'visible';
    if (isAppFocused) {
      if (playSound) {
        playChime();
      }
      return;
    }
  }

  if (playSound) {
    playChime();
  }

  // 1. Electron API Oficial: Nome oficial 'Visionary Studio', ícone e foco de janela
  if (window.electronAPI?.showNotification) {
    try {
      const res = await window.electronAPI.showNotification({ title, body: message, actionTab });
      if (res && res.success) return;
    } catch (err) {
      console.warn('Erro na notificação via Electron API:', err);
    }
  }

  // 2. Web Notification API nativa do navegador / WebView com handler de clique
  try {
    if ('Notification' in window) {
      const triggerWebNotif = () => {
        const notif = new Notification(title, { 
          body: message,
          icon: '/icon.png'
        });
        notif.onclick = () => {
          window.focus();
          if (window.electronAPI?.focusWindow) {
            window.electronAPI.focusWindow();
          }
          if (actionTab) {
            useWorkspaceStore.getState().setActiveTab(actionTab);
          }
        };
      };

      if (Notification.permission === 'granted') {
        triggerWebNotif();
        return;
      } else if (Notification.permission !== 'denied') {
        const permission = await Notification.requestPermission();
        if (permission === 'granted') {
          triggerWebNotif();
          return;
        }
      }
    }
  } catch (_) {}

  // 3. Fallback via Backend Python (Windows Runtime Toast Oficial)
  try {
    if (clientApi?.showSystemNotification) {
      await clientApi.showSystemNotification(title, message);
    }
  } catch (err) {
    console.warn('Falha ao enviar notificação do sistema:', err);
  }
}

