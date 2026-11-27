import { useState, useRef, useEffect, useCallback } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';

const DEV_USERS = {
  'trevo': "☾ '. 匚卄丹尺ㄥ工れＫ",
  'charlink': "☾ '. 匚卄丹尺ㄥ工れＫ",
  'admin': 'Administrador',
  'dev': 'Developer',
  'guest': 'Convidado Dev',
};

export const DEV_BOOT_LOGS = (userName) => [
  "VALIDANDO CREDENCIAIS: [•••••]... SUCESSO",
  "INICIALIZANDO SUBSISTEMAS DE DIAGNÓSTICO & GPU METRICS...",
  "ATIVANDO TEMA MONOCROMÁTICO // NOIR & WHITE...",
  "DESACOPLANDO AMBIENTE DE TESTES E CONTROLES...",
  `MODO DESENVOLVEDOR PRONTO // BEM-VINDO, ${userName}`,
];

export function useDevMode(applyDevTheme, restoreUserTheme, setActiveTab) {
  const [, setClickCount] = useState(0);
  const clickTimerRef = useRef(null);
  const devTimeoutsRef = useRef([]);
  
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [isDevUnlocked, setIsDevUnlocked] = useState(false);
  
  const [devTransition, setDevTransition] = useState(null); // null | 'loading'
  const [devLoadingProgress, setDevLoadingProgress] = useState(0);
  const [devLogIndex, setDevLogIndex] = useState(0);
  const [devLoadingFading, setDevLoadingFading] = useState(false);
  const [devUser, setDevUser] = useState(null);

  // Garante que o app nunca inicie em Modo Dev e limpa timers no unmount
  useEffect(() => {
    try {
      localStorage.removeItem('visionary:dev_unlocked');
    } catch (_) {}
    useWorkspaceStore.getState().setIsDevUnlocked?.(false);
    return () => {
      if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
      devTimeoutsRef.current.forEach(clearTimeout);
      devTimeoutsRef.current = [];
    };
  }, []);

  // Sincroniza estado de desbloqueio do modo dev no workspace store global
  useEffect(() => {
    useWorkspaceStore.getState().setIsDevUnlocked?.(isDevUnlocked);
  }, [isDevUnlocked]);

  const deactivateDevMode = useCallback(() => {
    setIsDevUnlocked(false);
    setDevUser(null);
    restoreUserTheme();
    const currentTab = useWorkspaceStore.getState().activeTab;
    if (currentTab === 'testes') {
      setActiveTab('processamento');
    }
  }, [restoreUserTheme, setActiveTab]);

  const handleSecretClick = useCallback((e) => {
    if (e) e.stopPropagation();
    if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
    
    setClickCount(prev => {
      const next = prev + 1;
      if (next >= 5) {
        if (isDevUnlocked) {
          deactivateDevMode();
        } else {
          setPasswordInput('');
          setPasswordError('');
          setShowPasswordModal(true);
        }
        return 0;
      }
      clickTimerRef.current = setTimeout(() => {
        setClickCount(0);
      }, 1500);
      return next;
    });
  }, [isDevUnlocked, deactivateDevMode]);

  const handlePasswordSubmit = useCallback((e) => {
    if (e) e.preventDefault();
    const cleanPwd = passwordInput.trim().toLowerCase();
    const identifiedUser = DEV_USERS[cleanPwd];

    if (identifiedUser) {
      setDevUser(identifiedUser);
      setShowPasswordModal(false);
      setPasswordInput('');
      setPasswordError('');

      setDevTransition('loading');
      setDevLoadingProgress(10);
      setDevLogIndex(0);
      setDevLoadingFading(false);
      devTimeoutsRef.current.forEach(clearTimeout);
      devTimeoutsRef.current = [];

      devTimeoutsRef.current.push(setTimeout(() => { 
        setDevLoadingProgress(32); 
        setDevLogIndex(1); 
      }, 800));

      devTimeoutsRef.current.push(setTimeout(() => { 
        setDevLoadingProgress(62); 
        setDevLogIndex(2); 
        applyDevTheme();
      }, 1600));

      devTimeoutsRef.current.push(setTimeout(() => { 
        setDevLoadingProgress(84); 
        setDevLogIndex(3); 
        setIsDevUnlocked(true);
        setActiveTab("testes");
      }, 2400));

      devTimeoutsRef.current.push(setTimeout(() => { 
        setDevLoadingProgress(100); 
        setDevLogIndex(4); 
      }, 3200));

      devTimeoutsRef.current.push(setTimeout(() => {
        setDevLoadingFading(true);
      }, 4500));

      devTimeoutsRef.current.push(setTimeout(() => {
        setDevTransition(null);
        setDevLoadingFading(false);
      }, 5100));
    } else {
      setPasswordError('Senha incorreta!');
    }
  }, [passwordInput, applyDevTheme, setActiveTab]);

  const skipDevLoading = useCallback(() => {
    if (devTransition === 'loading') {
      devTimeoutsRef.current.forEach(clearTimeout);
      devTimeoutsRef.current = [];
      setDevLoadingProgress(100);
      setDevLogIndex(4);
      applyDevTheme();
      setIsDevUnlocked(true);
      setActiveTab("testes");
      setDevTransition(null);
      setDevLoadingFading(false);
    }
  }, [devTransition, applyDevTheme, setActiveTab]);

  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      if (devTransition === 'loading' && (e.key === 'Enter' || e.key === 'Escape')) {
        e.preventDefault();
        skipDevLoading();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        if (isDevUnlocked) {
          deactivateDevMode();
        } else {
          setPasswordInput('');
          setPasswordError('');
          setShowPasswordModal(true);
        }
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [isDevUnlocked, devTransition, skipDevLoading, deactivateDevMode]);

  return {
    isDevUnlocked,
    setIsDevUnlocked,
    showPasswordModal,
    setShowPasswordModal,
    passwordInput,
    setPasswordInput,
    passwordError,
    setPasswordError,
    devTransition,
    devLoadingProgress,
    devLogIndex,
    devLoadingFading,
    devUser,
    handleSecretClick,
    handlePasswordSubmit,
    skipDevLoading,
    deactivateDevMode
  };
}
