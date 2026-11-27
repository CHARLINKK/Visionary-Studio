import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  isNotificationEnabled,
  setNotificationEnabled,
  isNotifyOnlyInBackground,
  setNotifyOnlyInBackground,
  sendNativeNotification,
} from '../notification';

describe('notification utilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('should toggle notification settings in localStorage', () => {
    expect(isNotificationEnabled()).toBe(true);
    setNotificationEnabled(false);
    expect(isNotificationEnabled()).toBe(false);

    expect(isNotifyOnlyInBackground()).toBe(true);
    setNotifyOnlyInBackground(false);
    expect(isNotifyOnlyInBackground()).toBe(false);
  });

  it('should suppress notification when disabled', async () => {
    setNotificationEnabled(false);
    await sendNativeNotification('Test Title', 'Test Message');
    expect(window.electronAPI.showNotification).not.toHaveBeenCalled();
  });

  it('should send notification via Electron API when in background', async () => {
    setNotificationEnabled(true);
    setNotifyOnlyInBackground(true);

    // Simulate window not focused
    vi.spyOn(document, 'hasFocus').mockReturnValue(false);

    await sendNativeNotification('Process Complete', 'Batch finished', { playSound: false });
    expect(window.electronAPI.showNotification).toHaveBeenCalledWith({
      title: 'Process Complete',
      body: 'Batch finished',
      actionTab: null,
    });
  });

  it('should bypass background check if force option is true', async () => {
    setNotificationEnabled(true);
    setNotifyOnlyInBackground(true);

    // App is focused
    vi.spyOn(document, 'hasFocus').mockReturnValue(true);
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });

    await sendNativeNotification('Forced Notice', 'Must show', { force: true, playSound: false });
    expect(window.electronAPI.showNotification).toHaveBeenCalledWith({
      title: 'Forced Notice',
      body: 'Must show',
      actionTab: null,
    });
  });

  it('should fallback to pywebview if electronAPI is absent', async () => {
    const originalElectron = window.electronAPI;
    delete window.electronAPI;

    vi.spyOn(document, 'hasFocus').mockReturnValue(false);

    await sendNativeNotification('Fallback Title', 'Fallback Body', { playSound: false });
    expect(window.pywebview.api.showSystemNotification).toHaveBeenCalledWith(
      'Fallback Title',
      'Fallback Body'
    );

    window.electronAPI = originalElectron;
  });
});
