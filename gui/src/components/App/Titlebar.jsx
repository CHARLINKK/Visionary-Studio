import { Minus, Square, Copy, X } from 'lucide-react';
import logoPng from '../../assets/logo3d.png';

export function Titlebar({ 
  isDevUnlocked, 
  devUser, 
  selectedFolder, 
  isMaximized, 
  handleToggleMaximize, 
  handleSecretClick,
  backgroundDownload,
  onOpenOnboarding
}) {
  return (
    <header className="custom-titlebar">
      <div 
        className="titlebar-info" 
        onClick={handleSecretClick} 
        onMouseDown={(e) => e.stopPropagation()} 
        style={{ cursor: 'default', userSelect: 'none', WebkitAppRegion: 'no-drag' }} 
        title={isDevUnlocked ? "Visionary Studio (Modo Dev)" : "Visionary Studio"}
      >
        <div className="titlebar-logo" style={{ pointerEvents: 'auto' }}>
          <img src={logoPng} alt="Visionary Studio" className="titlebar-logo-img" />
        </div>
        <span className="titlebar-brand">VISIONARY STUDIO</span>
        {isDevUnlocked && (
          <span className="titlebar-badge" style={{ backgroundColor: '#ffffff', color: '#000000' }}>
            {devUser ? `DEV // ${devUser}` : "DEV"}
          </span>
        )}
      </div>

      <div className="titlebar-drag-region">
        {selectedFolder?.name && (
          <span className="titlebar-active-file">
            {selectedFolder.name}
          </span>
        )}
        {backgroundDownload && (
          <button 
            type="button" 
            className="titlebar-bg-download-pill" 
            onClick={onOpenOnboarding} 
            title="Clique para ver o status dos modelos de IA"
          >
            <span className="download-spinner-dot" />
            <span>{backgroundDownload.text || `Baixando IA (${backgroundDownload.progress}%)`}</span>
          </button>
        )}
      </div>

      {window.electronAPI && (
        <div className="titlebar-controls">
          <button className="win-btn" onClick={() => window.electronAPI?.minimize()} title="Minimizar">
            <Minus size={13} />
          </button>
          <button className="win-btn" onClick={handleToggleMaximize} title={isMaximized ? "Restaurar" : "Maximizar"}>
            {isMaximized ? <Copy size={10} style={{ transform: 'rotate(90deg)' }} /> : <Square size={11} />}
          </button>
          <button className="win-btn win-btn-close" onClick={() => window.electronAPI?.close()} title="Fechar">
            <X size={14} />
          </button>
        </div>
      )}
    </header>
  );
}