import { memo, useState, useEffect } from 'react';
import { Minus, RefreshCw, Search, X, Folder, HardDrive, BookOpen } from 'lucide-react';
import LibrarySidebar from '../Library/LibrarySidebar';
import { useLibraryStore } from '../../stores/useLibraryStore';

const ExplorerItem = memo(function ExplorerItem({
  entry,
  isSelected,
  isChapter,
  showStatusDots,
  showPagePills,
  onClick,
}) {
  return (
    <div 
      className={`explorer-item ${isSelected ? 'active' : ''}`} 
      onClick={onClick}
      title={entry.name}
    >
      {entry.isDrive ? (
        <HardDrive size={16} />
      ) : isChapter ? (
        <BookOpen size={15} className="explorer-icon-chapter" />
      ) : (
        <Folder size={16} className="explorer-icon-folder" />
      )}
      <div className="item-content-wrap">
        <span className="item-name">{entry.name}</span>
        {showStatusDots && (entry.status === 'green' || entry.status === 'progress' || entry.status === 'blue') && (
          <span 
            className={`explorer-status-dot ${entry.status}`} 
            title={
              entry.status === 'green' ? 'Traduzido / Concluído' :
              entry.status === 'progress' ? 'Em andamento' : 'Pasta organizadora'
            }
          />
        )}
        {showPagePills && entry.imgCount > 0 && (
          <span className="explorer-page-pill" title={`${entry.imgCount} páginas`}>
            {entry.imgCount === 1 ? '1 pág' : `${entry.imgCount} págs`}
          </span>
        )}
      </div>
    </div>
  );
});

export function ExplorerSidebar({
  activeTab,
  isSidebarOpen,
  setIsSidebarOpen,
  sidebarWidth,
  isResizing,
  startResize,
  handleSecretClick,
  handleGoUp,
  isAtRoot,
  currentPath,
  refreshCurrentDirectory,
  searchQuery,
  setSearchQuery,
  filteredEntries,
  handleEntryClick,
  selectedFolder,
  showStatusDots,
  showPagePills
}) {
  const [isMounted, setIsMounted] = useState(false);
  const isLibLoading = useLibraryStore((s) => s.isLoading);

  useEffect(() => {
    const timer = setTimeout(() => setIsMounted(true), 150);
    return () => clearTimeout(timer);
  }, []);

  return (
    <aside 
      className={`app-sidebar ${!isSidebarOpen ? 'collapsed' : ''}`} 
      style={{ 
        width: isSidebarOpen ? sidebarWidth : 0, 
        overflow: 'hidden', 
        transition: (!isMounted || isResizing) ? 'none' : 'width 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
        userSelect: isResizing ? 'none' : undefined,
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {activeTab === 'biblioteca' ? (
        <LibrarySidebar
          sidebarCollapsed={false}
          setSidebarCollapsed={(val) => { if (val) setIsSidebarOpen(false); }}
          openLibraryFolder={() => useLibraryStore.getState().requestOpenLibraryFolder()}
          refreshLibrary={() => useLibraryStore.getState().bumpLibraryRevision()}
          isLoading={isLibLoading}
          loadLibraryFile={(f) => useLibraryStore.getState().requestLoadFile(f)}
          deleteLibraryFile={(e, f) => useLibraryStore.getState().requestDeleteFile(f)}
        />
      ) : (
        <>
          <div className="sidebar-header" onClick={handleSecretClick} style={{ cursor: 'default', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ userSelect: 'none' }}>EXPLORADOR</h3>
            <button 
              className="btn-lib-icon btn-toggle-sidebar" 
              onClick={(e) => { e.stopPropagation(); setIsSidebarOpen(false); }}
              title="Recolher Explorador"
            >
              <Minus size={15} />
            </button>
          </div>
          
          <div className="explorer-toolbar">
            <div className="explorer-nav-row">
              <button 
                className="btn-explorer-up" 
                onClick={handleGoUp} 
                disabled={isAtRoot}
                title={isAtRoot ? 'Discos' : `Subir nível (${currentPath?.split(/[\\/]/).filter(Boolean).pop() || '...'})`}
              >
                ↑ {isAtRoot ? 'Discos' : currentPath?.split(/[\\/]/).filter(Boolean).pop() || '...'}
              </button>
              <button 
                className="btn-explorer-refresh" 
                onClick={refreshCurrentDirectory} 
                title="Atualizar lista e status em tempo real"
              >
                <RefreshCw size={12} />
              </button>
            </div>
            
            <div className="explorer-search-box">
              <Search size={13} className="explorer-search-icon" />
              <input 
                type="text" 
                className="explorer-search-input"
                placeholder={isAtRoot ? "Filtrar discos..." : "Buscar capítulos (ex: cap 1)..."}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.stopPropagation()}
                onKeyUp={(e) => e.stopPropagation()}
              />
              {searchQuery && (
                <button 
                  className="explorer-search-clear" 
                  onClick={() => setSearchQuery('')}
                  title="Limpar busca"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          <div className="explorer-list">
            {(() => {
              const displayEntries = filteredEntries.filter(entry => entry.isDrive || entry.isBack || entry.isDir);
              if (displayEntries.length === 0 && searchQuery) {
                return (
                  <div style={{ padding: '16px 8px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '11.5px' }}>
                    Nenhum item encontrado
                  </div>
                );
              }
              if (displayEntries.length === 0 && !searchQuery && !isAtRoot) {
                return (
                  <div style={{ padding: '16px 8px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '11.5px' }}>
                    Nenhum capítulo ou pasta encontrado
                  </div>
                );
              }
              return displayEntries.map((entry, idx) => {
                const isSelected = selectedFolder?.path === entry.path;
                const isChapter = entry.isChapter || (entry.isDir && entry.hasImages);

                return (
                  <ExplorerItem
                    key={entry.path || idx}
                    entry={entry}
                    isSelected={isSelected}
                    isChapter={isChapter}
                    showStatusDots={showStatusDots}
                    showPagePills={showPagePills}
                    onClick={() => handleEntryClick(entry)}
                  />
                );
              });
            })()}
          </div>
        </>
      )}

      {isSidebarOpen && (
        <div 
          className={`sidebar-resize-handle ${isResizing ? 'active' : ''}`} 
          onMouseDown={startResize}
          title="Arrastar para redimensionar"
        />
      )}
    </aside>
  );
}
