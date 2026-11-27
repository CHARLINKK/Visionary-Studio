import { clientApi } from '../api/bridge';

/**
 * Utilitário universal de cópia para área de transferência.
 * Ordem de resolução:
 * 1. navigator.clipboard.writeText (Web API assíncrona)
 * 2. window.electronAPI.copyToClipboard (IPC nativo do Electron)
 * 3. clientApi.copyToClipboard (Fallback do backend Python)
 */
export async function copyTextToClipboard(text) {
  if (typeof text !== 'string') text = String(text ?? '');
  if (!text) return false;

  // 1. API Moderna do Navegador
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Segue para fallback nativo
  }

  // 2. API Nativa do Electron (IPC)
  try {
    if (typeof window !== 'undefined' && window.electronAPI?.copyToClipboard) {
      const res = await window.electronAPI.copyToClipboard(text);
      if (res && res.success) return true;
    }
  } catch {
    // Segue para fallback do backend
  }

  // 3. Fallback Nativo do Sistema via Backend RPC
  try {
    if (clientApi?.copyToClipboard) {
      const res = await clientApi.copyToClipboard(text);
      if (res && res.success) return true;
    }
  } catch (err) {
    console.error('Todos os métodos de cópia falharam:', err);
  }

  return false;
}

