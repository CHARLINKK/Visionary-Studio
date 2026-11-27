import React from 'react';
import { 
  Folder, Check, CheckSquare, XSquare, 
  RotateCcw, Columns, Scissors, Trash2, 
  ZoomIn, ZoomOut, RefreshCw, HelpCircle, X
} from 'lucide-react';

export default function LightboxToolbar({
  activeChapterPath,
  chapterFolderName,
  imagesCount,
  selectedCount,
  selectAll,
  clearSelection,
  readingDirection,
  setReadingDirection,
  handleMerge,
  handleSplit,
  handleDelete,
  hasUnsavedOrder,
  applyOrder,
  discardOrder,
  isProcessing,
  handleZoomChange,
  gridColumns,
  loadImages,
  showHelp,
  setShowHelp,
  helpPopoverRef
}) {
  return (
    <div className="lightbox-unified-toolbar">
      {/* ESQUERDA: IDENTIFICADOR DO CAPÍTULO E SELEÇÃO */}
      <div className="toolbar-left">
        <div className="chapter-badge" title={activeChapterPath}>
          <Folder size={13} className="chapter-icon" />
          <span className="chapter-name">{chapterFolderName}</span>
          <span className="chapter-count">{imagesCount} {imagesCount === 1 ? 'pág' : 'págs'}</span>
        </div>

        {selectedCount > 0 && (
          <div className="selection-badge">
            <Check size={11} strokeWidth={3} />
            <span>{selectedCount} {selectedCount === 1 ? 'selecionada' : 'selecionadas'}</span>
          </div>
        )}
      </div>

      {/* CENTRO: GRUPOS DE AÇÃO COMPACTOS */}
      <div className="toolbar-center">
        {/* SELEÇÃO */}
        <div className="action-pill-group">
          <button 
            className="toolbar-btn" 
            onClick={selectAll} 
            disabled={imagesCount === 0}
            title="Selecionar todas as páginas do capítulo"
          >
            <CheckSquare size={13} />
            <span>Tudo</span>
          </button>
          <button 
            className="toolbar-btn" 
            onClick={clearSelection} 
            disabled={selectedCount === 0}
            title="Limpar seleção atual"
          >
            <XSquare size={13} />
            <span>Limpar</span>
          </button>
        </div>

        <div className="toolbar-divider" />

        {/* TRATAMENTO DE PÁGINAS DUPLAS E SPREADS */}
        <div className="action-pill-group">
          {selectedCount >= 2 && (
            <div className="stitch-select-wrapper" title="Sentido de costura ao unir duas páginas">
              <span className="stitch-label">Costura:</span>
              <select 
                className="stitch-dropdown" 
                value={readingDirection} 
                onChange={e => setReadingDirection(e.target.value)}
              >
                <option value="rtl">Mangá (Dir ➔ Esq)</option>
                <option value="ltr">Ocidental (Esq ➔ Dir)</option>
              </select>
            </div>
          )}

          <button 
            className="toolbar-btn" 
            onClick={handleMerge} 
            disabled={selectedCount < 2 || isProcessing || hasUnsavedOrder}
            title={
              hasUnsavedOrder
                ? "Salve ou descarte a nova ordem das páginas antes de unir"
                : selectedCount < 2
                  ? "Selecione ao menos 2 páginas para unir em cena dupla"
                  : "Unir páginas selecionadas lado a lado"
            }
          >
            <Columns size={13} />
            <span>Unir Páginas ({selectedCount})</span>
          </button>

          <button 
            className="toolbar-btn" 
            onClick={handleSplit} 
            disabled={selectedCount !== 1 || isProcessing || hasUnsavedOrder}
            title={
              hasUnsavedOrder
                ? "Salve ou descarte a nova ordem das páginas antes de dividir"
                : selectedCount !== 1
                  ? "Selecione exatamente 1 página dupla para dividir"
                  : "Dividir página dupla selecionada em duas metades verticais"
            }
          >
            <Scissors size={13} />
            <span>Dividir</span>
          </button>
        </div>

        <div className="toolbar-divider" />

        {/* EXCLUSÃO */}
        <div className="action-pill-group">
          <button 
            className="toolbar-btn danger" 
            onClick={handleDelete} 
            disabled={selectedCount === 0 || isProcessing}
            title="Excluir páginas selecionadas permanentemente da pasta"
          >
            <Trash2 size={13} />
            <span>Excluir ({selectedCount})</span>
          </button>
        </div>

        {/* BOTÃO DE SALVAR OU DESCARTAR ORDEM */}
        {hasUnsavedOrder && (
          <>
            <div className="toolbar-divider" />
            <div className="action-pill-group reorder-alert-group">
              <button 
                className="toolbar-btn primary-save glow btn-save-order" 
                onClick={applyOrder} 
                disabled={isProcessing}
                title="Salvar nova ordem das páginas no disco físico"
              >
                <RotateCcw size={13} className={isProcessing ? 'spin' : ''} />
                <span>Salvar Ordem</span>
              </button>
              <button 
                className="toolbar-btn btn-discard-order" 
                onClick={discardOrder} 
                disabled={isProcessing}
                title="Descartar alterações e restaurar ordem do disco"
              >
                <X size={13} />
                <span>Descartar</span>
              </button>
            </div>
          </>
        )}
      </div>

      {/* DIREITA: ZOOM, REFRESH E AJUDA */}
      <div className="toolbar-right">
        {/* CONTROLE DE COLUNAS / DENSIDADE */}
        <div className="action-pill-group zoom-group">
          <button 
            className="toolbar-btn icon-only" 
            onClick={() => handleZoomChange(1)} 
            disabled={gridColumns >= 8}
            title="Mais colunas por linha (cards menores)"
            aria-label="Mais colunas por linha"
          >
            <ZoomOut size={13} />
          </button>
          <span 
            className="zoom-indicator" 
            title={`Densidade: ${gridColumns} ${gridColumns === 1 ? 'coluna' : 'colunas'} por linha (clique para alternar)`}
            onClick={() => handleZoomChange(gridColumns === 4 ? -2 : (gridColumns >= 6 ? -(gridColumns - 1) : 1))}
            style={{ cursor: 'pointer', userSelect: 'none' }}
          >
            {gridColumns} col
          </span>
          <button 
            className="toolbar-btn icon-only" 
            onClick={() => handleZoomChange(-1)} 
            disabled={gridColumns <= 1}
            title="Menos colunas por linha (cards maiores)"
            aria-label="Menos colunas por linha"
          >
            <ZoomIn size={13} />
          </button>
        </div>

        {/* REFRESH */}
        <button 
          className="toolbar-btn icon-only" 
          onClick={() => loadImages()} 
          disabled={isProcessing}
          title="Recarregar imagens da pasta do capítulo"
        >
          <RefreshCw size={13} className={isProcessing ? 'spin' : ''} />
        </button>

        {/* AJUDA / GUIA PRO */}
        <div className="help-wrapper">
          <button 
            className={`toolbar-btn icon-only btn-help ${showHelp ? 'active' : ''}`} 
            onClick={() => setShowHelp(prev => !prev)}
            title="Dicas de uso da Lightbox"
          >
            <HelpCircle size={14} />
          </button>

          {showHelp && (
            <div className="lightbox-help-popover" ref={helpPopoverRef}>
              <div className="help-popover-header">
                <strong>Guia Rápido da Lightbox</strong>
                <button 
                  type="button" 
                  className="close-help-btn" 
                  title="Fechar guia"
                  onClick={() => setShowHelp(false)}
                >
                  <X size={12} />
                </button>
              </div>
              <ul className="help-popover-list">
                <li><span className="key-tag">2x Clique</span> <span>Abre a página diretamente no Estúdio</span></li>
                <li><span className="key-tag">Espaço</span> <span>Pré-visualização rápida em tela cheia (Quick Look)</span></li>
                <li><span className="key-tag">Shift + Clique</span> <span>Seleciona uma faixa de páginas contínuas</span></li>
                <li><span className="key-tag">Arrastar</span> <span>Reordena páginas (clique em <em>Salvar Ordem</em>)</span></li>
                <li><span className="key-tag">Unir</span> <span>Junta 2+ páginas em spread horizontal (dupla)</span></li>
                <li><span className="key-tag">Dividir</span> <span>Divide 1 página ao meio (sentido da leitura)</span></li>
                <li><span className="key-tag">Delete</span> <span>Exclui as páginas selecionadas do disco</span></li>
                <li><span className="key-tag">Ctrl + A / Esc</span> <span>Selecionar tudo / Limpar seleção</span></li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
