import { useRef, useState, useLayoutEffect, useMemo } from 'react';
import { 
  Layers, 
  BookOpen, 
  LayoutDashboard, 
  Cpu, 
  Settings as SettingsIcon, 
  HelpCircle, 
  Wrench, 
  Folder, 
  FileText,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Zap
} from 'lucide-react';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import { useToast } from '../../contexts/ToastContext';
import { clientApi } from '../../api/bridge';

export function AppTabs({ 
  activeTab, 
  handleTabChange, 
  onPrefetchTab,
  isSidebarOpen, 
  setIsSidebarOpen, 
  selectedFolder, 
  isDevUnlocked,
  isHelpInspectorActive = false,
  onToggleHelpInspector
}) {
  const tabsNavRef = useRef(null);
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 0, opacity: 0 });

  const { statusFlash } = useToast() || {};
  const rawJobQueue = useWorkspaceStore((s) => s.jobQueue);
  const jobQueue = useMemo(() => rawJobQueue || [], [rawJobQueue]);

  // Tarefa de pipeline atualmente em execução
  const runningJob = useMemo(() => {
    return jobQueue.find(j => j.status === 'running' || j.status === 'pending');
  }, [jobQueue]);

  const folderPath = selectedFolder?.path || '';
  const folderDisplayName = useMemo(() => {
    if (!folderPath) return null;
    return folderPath.split(/[/\\]/).slice(-2).join(' / ');
  }, [folderPath]);

  const handleOpenFolder = () => {
    if (folderPath && clientApi?.openFileInExplorer) {
      clientApi.openFileInExplorer(folderPath);
    }
  };

  useLayoutEffect(() => {
    if (!tabsNavRef.current) return;
    const updatePill = () => {
      const activeBtn = tabsNavRef.current.querySelector(`.tab-btn[data-tab="${activeTab}"]`);
      if (activeBtn) {
        setPillStyle({
          left: activeBtn.offsetLeft,
          width: activeBtn.offsetWidth,
          opacity: 1
        });
      } else {
        setPillStyle((prev) => ({
          ...prev,
          opacity: 0
        }));
      }
    };
    
    updatePill();

    const resizeObserver = new ResizeObserver(() => {
      updatePill();
    });
    
    resizeObserver.observe(tabsNavRef.current);
    const buttons = tabsNavRef.current.querySelectorAll('.tab-btn');
    buttons.forEach(btn => resizeObserver.observe(btn));

    return () => resizeObserver.disconnect();
  }, [activeTab, isDevUnlocked]);

  return (
    <nav className="top-tabs" aria-label="Navegação principal">
      {!isSidebarOpen && (
        <button 
          className="btn-expand-sidebar" 
          onClick={() => setIsSidebarOpen(true)}
          title={activeTab === 'biblioteca' ? "Expandir Capítulos" : "Expandir Explorador de Arquivos"}
          style={{ 
            marginRight: '8px', 
            padding: '6px 10px', 
            background: 'var(--bg-surface)', 
            border: '1px solid var(--border-subtle)', 
            borderRadius: 'var(--radius-sm)', 
            color: 'var(--text-main)', 
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            fontWeight: '500'
          }}
        >
          {activeTab === 'biblioteca' ? (
            <><FileText size={13} /> Capítulos</>
          ) : (
            <><Folder size={13} /> Explorador</>
          )}
        </button>
      )}

      <div className="tabs-pill-nav" ref={tabsNavRef}>
        <div 
          className="tab-indicator-pill" 
          style={{ 
            transform: `translateX(${pillStyle.left}px)`, 
            width: `${pillStyle.width}px`, 
            opacity: pillStyle.opacity 
          }} 
        />
        <button data-tab="processamento" className={`tab-btn ${activeTab === 'processamento' ? 'active' : ''}`} onClick={() => handleTabChange('processamento')}>
          <Layers size={14} /> Estúdio
        </button>
        <button data-tab="biblioteca" className={`tab-btn ${activeTab === 'biblioteca' ? 'active' : ''}`} onMouseEnter={() => onPrefetchTab?.('biblioteca')} onFocus={() => onPrefetchTab?.('biblioteca')} onClick={() => handleTabChange('biblioteca')}>
          <BookOpen size={14} /> Biblioteca
        </button>
        <button 
          data-tab="lightbox" 
          className={`tab-btn ${activeTab === 'lightbox' ? 'active' : ''}`} 
          onMouseEnter={() => onPrefetchTab?.('lightbox')}
          onFocus={() => onPrefetchTab?.('lightbox')}
          onClick={() => handleTabChange('lightbox')}
          title="Lightbox: Mesa de Preparação & Montagem de Páginas"
        >
          <LayoutDashboard size={14} /> Lightbox
        </button>
        <button data-tab="modulos" className={`tab-btn ${activeTab === 'modulos' ? 'active' : ''}`} onMouseEnter={() => onPrefetchTab?.('modulos')} onFocus={() => onPrefetchTab?.('modulos')} onClick={() => handleTabChange('modulos')}>
          <Cpu size={14} /> Módulos
        </button>
        <button data-tab="configuracoes" className={`tab-btn ${activeTab === 'configuracoes' ? 'active' : ''}`} onMouseEnter={() => onPrefetchTab?.('configuracoes')} onFocus={() => onPrefetchTab?.('configuracoes')} onClick={() => handleTabChange('configuracoes')}>
          <SettingsIcon size={14} /> Configurações
        </button>
        {isDevUnlocked && (
          <button data-tab="testes" className={`tab-btn ${activeTab === 'testes' ? 'active' : ''}`} onClick={() => handleTabChange('testes')}>
            <Wrench size={14} /> Diagnóstico
          </button>
        )}
      </div>

      <div className="top-tabs-actions">
        {/* 1. Status Flash Transitório ou Pipeline em Execução */}
        {statusFlash ? (
          <div className={`tab-status-pill flash-${statusFlash.type || 'info'} fade-in`}>
            {statusFlash.type === 'error' ? (
              <AlertCircle size={12} className="text-rose-400" />
            ) : statusFlash.type === 'warning' ? (
              <AlertTriangle size={12} className="text-amber-400" />
            ) : statusFlash.type === 'success' ? (
              <CheckCircle2 size={12} className="text-emerald-400" />
            ) : (
              <span className="tab-status-dot-pulse" />
            )}
            <span className="tab-status-text">{statusFlash.text}</span>
          </div>
        ) : runningJob ? (
          <div className="tab-status-pill pill-pipeline" title="Processamento de páginas em segundo plano">
            <span className="status-pulse-spinner" />
            <span className="tab-status-text">
              Pipeline: <strong>{runningJob.currentStepLabel || 'Processando'}</strong>
              {runningJob.progress !== undefined ? ` • ${Math.round(runningJob.progress)}%` : ''}
            </span>
          </div>
        ) : null}

        {/* 2. Pasta / Capítulo Ativo */}
        {folderDisplayName && (
          <button 
            type="button"
            className="tab-folder-pill"
            onClick={handleOpenFolder}
            title={`${folderPath}\n(Clique para abrir no Windows Explorer)`}
          >
            <Folder size={12} className="tab-folder-icon" />
            <span className="tab-folder-text">{folderDisplayName}</span>
            <ExternalLink size={10} className="tab-folder-ext" />
          </button>
        )}

        {/* 3. Aceleração CUDA */}
        <div className="tab-hw-pill" title="Aceleração por Hardware PyTorch (CUDA)">
          <Zap size={10} className="text-amber-400" />
          <span>CUDA</span>
        </div>

        {/* 4. Inspetor de Ajuda */}
        <button
          type="button"
          data-help-id="help-inspector-toggle"
          className={`btn-inspector-toggle ${isHelpInspectorActive ? 'is-active' : ''}`}
          onClick={() => {
            if (onToggleHelpInspector) {
              onToggleHelpInspector();
            }
          }}
          title={
            isHelpInspectorActive
              ? "Desativar Inspetor de Ajuda (F1 ou Esc)"
              : "Modo Inspetor de Ajuda (F1)"
          }
          aria-label="Inspetor de Ajuda (F1)"
        >
          <HelpCircle size={14} className="btn-inspector-icon" />
        </button>
      </div>
    </nav>
  );
}
export default AppTabs;
