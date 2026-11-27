import { useState, useEffect } from 'react';

export function useWindowControls() {
  const [isMaximized, setIsMaximized] = useState(true);

  useEffect(() => {
    const syncState = async () => {
      try {
        if (window.electronAPI?.isMaximized) {
          const state = await window.electronAPI.isMaximized();
          setIsMaximized(state);
        }
      } catch (_) {}
    };
    
    syncState();
    const timer = setTimeout(syncState, 300);

    const handleResize = () => {
      syncState();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const handleToggleMaximize = async () => {
    if (window.electronAPI?.toggleMaximize) {
      const nextState = await window.electronAPI.toggleMaximize();
      setIsMaximized(nextState);
    }
  };

  return { isMaximized, handleToggleMaximize };
}
