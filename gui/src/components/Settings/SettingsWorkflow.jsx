import { FolderOpen } from 'lucide-react';
import { ModernCheckbox } from './ModernCheckbox';

export function SettingsWorkflow({
  baseFolder, baseFolderInput, setBaseFolderInput,
  applyBaseFolder, handleBrowseFolder, handleClearBaseFolder,
  showPagePills, setShowPagePills, showStatusDots, setShowStatusDots,
  autoResumePending, handleToggleAutoResume,
  autoTurnPage, handleToggleAutoTurnPage,
  autoZoomLibrary, handleToggleAutoZoomLibrary,
  quickSymbols, handleToggleQuickSymbols
}) {
  return (
    <div className="settings-section workflow-section">
      <div className="workflow-settings-card">
        <div className="workflow-block">
          <div className="workflow-header">
            <span className="workflow-title">Diretório Raiz do Explorador</span>
            <span className="workflow-desc">
              Pasta padrão de trabalho montada na árvore lateral ao iniciar o Visionary.
            </span>
          </div>

          <div className="workflow-path-bar">
            <div className="workflow-path-input-wrap">
              <FolderOpen size={15} className="workflow-path-icon" />
              <input
                className="workflow-path-input"
                type="text"
                placeholder="Navegação livre (Meu Computador) — insira um caminho ou clique em Navegar..."
                value={baseFolderInput}
                onChange={e => setBaseFolderInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') applyBaseFolder(); }}
                spellCheck={false}
              />
            </div>
            <div className="workflow-path-actions">
              <button
                className="workflow-btn-browse"
                onClick={handleBrowseFolder}
                title="Abrir janela nativa do Windows para selecionar pasta"
              >
                <FolderOpen size={13} />
                <span>Navegar...</span>
              </button>
              <button
                className={`workflow-btn-apply ${baseFolderInput.trim() !== (baseFolder || '') ? 'is-dirty' : ''}`}
                onClick={() => applyBaseFolder()}
                title="Fixar este caminho como raiz padrão"
              >
                Aplicar
              </button>
              {baseFolderInput && (
                <button
                  className="workflow-btn-clear"
                  onClick={handleClearBaseFolder}
                  title="Redefinir para navegação livre no sistema"
                >
                  Limpar
                </button>
              )}
            </div>
          </div>

          <div className="workflow-status-telemetry">
            <span className={`workflow-status-dot ${baseFolder ? 'is-active' : ''}`} />
            <span className="workflow-status-text">
              {baseFolder ? (
                <>
                  <strong className="workflow-status-label">Raiz Fixada:</strong>
                  <span className="workflow-status-path">{baseFolder}</span>
                </>
              ) : (
                <>
                  <strong className="workflow-status-label">Modo Ativo:</strong>
                  <span>Navegação livre em todas as unidades (Meu Computador)</span>
                </>
              )}
            </span>
          </div>
        </div>

        <div className="workflow-card-divider" />

        <div className="workflow-grid-split">
          <div className="workflow-col">
            <div className="workflow-header">
              <span className="workflow-title">Explorador Lateral</span>
              <span className="workflow-desc">Sinalizações visuais na árvore de pastas.</span>
            </div>
            <div className="modern-checkboxes-stack">
              <ModernCheckbox
                checked={showPagePills}
                onChange={setShowPagePills}
                label="Contador de Páginas"
                description="Exibe etiquetas com o total de páginas detectadas no capítulo."
                badge="Explorador"
              />
              <ModernCheckbox
                checked={showStatusDots}
                onChange={setShowStatusDots}
                label="Indicador de Status"
                description="Ponto visual indicando o estado de tradução dos capítulos."
                badge="Status"
              />
            </div>
          </div>

          <div className="workflow-col">
            <div className="workflow-header">
              <span className="workflow-title">Biblioteca & Letreiramento</span>
              <span className="workflow-desc">Automações de foco contínuo e navegação.</span>
            </div>
            <div className="modern-checkboxes-stack">
              <ModernCheckbox
                checked={autoResumePending}
                onChange={handleToggleAutoResume}
                label="Auto-Retomar na 1ª Pendente"
                description="Salta direto para a primeira página com falas não copiadas."
                badge="Produtividade"
              />
              <ModernCheckbox
                checked={autoTurnPage}
                onChange={handleToggleAutoTurnPage}
                label="Auto-Avanço de Página"
                description="Passa para a próxima página ao copiar o último balão."
                badge="Automação"
              />
              <ModernCheckbox
                checked={autoZoomLibrary}
                onChange={handleToggleAutoZoomLibrary}
                label="Auto-Zoom nos Balões"
                description="Centraliza e aproxima o balão ativo no modo lado a lado."
                badge="Visual"
              />
              <ModernCheckbox
                checked={quickSymbols}
                onChange={handleToggleQuickSymbols}
                label="Teclado Virtual de Símbolos"
                description="Minibarra flutuante para pontuação e caracteres especiais."
                badge="Acessibilidade"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
