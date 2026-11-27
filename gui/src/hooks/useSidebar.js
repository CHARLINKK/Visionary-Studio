import { useState, useRef, useCallback } from 'react';
import { clientApi } from '../api/bridge';

export function useSidebar() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    try {
      const saved = localStorage.getItem('visionary:sidebar_width');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= 180 && parsed <= 600) return parsed;
      }
    } catch (_) {}
    return 260;
  });
  
  const [isResizing, setIsResizing] = useState(false);
  const sidebarWidthRef = useRef(sidebarWidth);
  sidebarWidthRef.current = sidebarWidth;

  const startResize = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    const startX = e.clientX;
    const startW = sidebarWidthRef.current;
    let resizeRafId = null;

    const onMouseMove = (moveEvent) => {
      if (resizeRafId) return;
      resizeRafId = requestAnimationFrame(() => {
        resizeRafId = null;
        const newWidth = Math.max(180, Math.min(600, startW + (moveEvent.clientX - startX)));
        setSidebarWidth(newWidth);
      });
    };

    const onMouseUp = (upEvent) => {
      if (resizeRafId) {
        cancelAnimationFrame(resizeRafId);
        resizeRafId = null;
      }
      const finalWidth = Math.max(180, Math.min(600, startW + (upEvent.clientX - startX)));
      setSidebarWidth(finalWidth);
      setIsResizing(false);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      try {
        localStorage.setItem('visionary:sidebar_width', finalWidth.toString());
      } catch (_) {}
      clientApi.saveSettings({ sidebarWidth: finalWidth }).catch(() => {});
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, []);

  return { isSidebarOpen, setIsSidebarOpen, sidebarWidth, setSidebarWidth, isResizing, startResize };
}
