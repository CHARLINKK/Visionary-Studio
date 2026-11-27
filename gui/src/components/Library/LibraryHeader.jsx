import React, { useState, useMemo } from "react";
import {
  FolderOpen, Copy, Check, FileText, ChevronDown, ChevronRight,
  ChevronUp, Search, Download, Edit3, X, RotateCcw, ChevronLeft, RefreshCw,
  Columns, AlignLeft, SkipForward, ChevronsUpDown, Bookmark
} from "lucide-react";
import { useLibraryStore } from "../../stores/useLibraryStore";

const isMac = typeof navigator !== "undefined" && navigator.platform?.toUpperCase().indexOf("MAC") >= 0;

export const LibraryHeader = React.memo(function LibraryHeader(props) {
  const c = props.controller || props;

  const storeTypographyRules = useLibraryStore((s) => s.typographyRules);
  const storeUpdateTypographyRules = useLibraryStore((s) => s.updateTypographyRules);
  const storeAutoResumePending = useLibraryStore((s) => s.autoResumePending);
  const storeSetAutoResumePending = useLibraryStore((s) => s.setAutoResumePending);

  const [localTypographyOpen, setLocalTypographyOpen] = useState(false);
  const [localExportOpen, setLocalExportOpen] = useState(false);

  const activeFile = c.activeFile;
  const parsedPages = useMemo(() => c.parsedPages || [], [c.parsedPages]);
  const totalBalloons = c.totalBalloons || 0;
  const copiedBalloons = c.copiedBalloons || 0;
  const progressPercentage = c.progressPercentage || 0;
  const activePageIndex = c.activePageIndex ?? 0;
  const activePageData = c.activePageData;
  const resetProgress = c.resetProgress;
  const jumpToNextPending = c.jumpToNextPending;
  const openInExplorer = c.openInExplorer;

  const isTypographyRulesOpen = c.isTypographyRulesOpen !== undefined ? c.isTypographyRulesOpen : localTypographyOpen;
  const setIsTypographyRulesOpen = c.setIsTypographyRulesOpen || setLocalTypographyOpen;
  const typographyRules = c.typographyRules || storeTypographyRules;
  const updateTypographyRules = c.updateTypographyRules || storeUpdateTypographyRules;

  const isExportMenuOpen = c.isExportMenuOpen !== undefined ? c.isExportMenuOpen : localExportOpen;
  const setIsExportMenuOpen = c.setIsExportMenuOpen || setLocalExportOpen;
  const exportScript = c.exportScript;
  const syncChapterTxt = c.syncChapterTxt;
  const isSyncing = c.isSyncing;
  const collapsedPages = useMemo(() => c.collapsedPages || {}, [c.collapsedPages]);
  const setCollapsedPages = c.setCollapsedPages;
  const copyRawContent = c.copyRawContent;
  const isRawCopied = c.isRawCopied;
  const viewMode = c.viewMode;
  const changeViewMode = c.changeViewMode;
  const goToPage = c.goToPage;
  const autoResumePending = c.autoResumePending !== undefined ? c.autoResumePending : storeAutoResumePending;
  const toggleAutoResume = c.toggleAutoResume || (() => storeSetAutoResumePending(!storeAutoResumePending));
  const searchInputRef = c.searchInputRef;
  const activeSearchQuery = c.activeSearchQuery || "";
  const setActiveSearchQuery = c.setActiveSearchQuery;
  const searchMatches = c.searchMatches || [];
  const currentMatchIndex = c.currentMatchIndex || 0;
  const handlePrevSearchMatch = c.handlePrevSearchMatch;
  const handleNextSearchMatch = c.handleNextSearchMatch;
  const clearSearch = c.clearSearch;
  const copyFullPage = c.copyFullPage;
  const openInStudio = c.openInStudio;

  const isAllExpanded = useMemo(() => {
    return parsedPages.length > 0 && parsedPages.every((p) => !collapsedPages[p.pageNumber]);
  }, [parsedPages, collapsedPages]);

  return (
    <div className="content-header">
      <div className="content-header-left">
        <h2 className="chapter-main-title" title={activeFile?.name}>
          {activeFile?.name?.replace(/\.txt$/i, "")}
        </h2>
        {parsedPages.length > 0 && (
          <div className="chapter-page-count">{parsedPages.length} Págs</div>
        )}
        {totalBalloons > 0 && viewMode === "script" && (
          <div className="chapter-progress-pill" title="Progresso de balões copiados">
            <div>
              {copiedBalloons}/{totalBalloons} ({progressPercentage}%)
            </div>
            <div className="mini-progress-bar">
              <div className="mini-progress-fill" style={{ width: `${progressPercentage}%` }} />
            </div>
            {copiedBalloons > 0 && (
              <div className="btn-mini-reset" onClick={resetProgress} title="Reiniciar progresso">
                <RotateCcw size={10} />
              </div>
            )}
          </div>
        )}
        <button
          type="button"
          className="btn-path-icon"
          onClick={() => openInExplorer?.(activeFile?.chapter_dir || activeFile?.path)}
          title="Abrir pasta no Explorer"
        >
          <FolderOpen size={13} />
        </button>

        {viewMode === "split" && parsedPages.length > 0 && (
          <div className="split-nav-pill">
            <button
              type="button"
              className="btn-split-nav"
              onClick={() => goToPage?.(activePageIndex - 1)}
              disabled={activePageIndex <= 0}
              title="Página anterior"
            >
              <ChevronLeft size={13} />
            </button>
            <div className="split-nav-label">
              Pág. {String(activePageData?.pageNumber || activePageIndex + 1).padStart(2, "0")} / {String(parsedPages.length).padStart(2, "0")}
            </div>
            <button
              type="button"
              className="btn-split-nav"
              onClick={() => goToPage?.(activePageIndex + 1)}
              disabled={activePageIndex >= parsedPages.length - 1}
              title="Próxima página"
            >
              <ChevronRight size={13} />
            </button>
            {totalBalloons > 0 && progressPercentage < 100 && (
              <button
                type="button"
                className="btn-split-nav btn-jump-pending"
                onClick={jumpToNextPending}
                title="Saltar para a primeira página com falas ainda não copiadas"
              >
                <SkipForward size={11} />
                <span>Próxima Pendente</span>
              </button>
            )}
            <button
              type="button"
              className={`btn-split-nav btn-auto-resume-icon ${autoResumePending ? "active" : ""}`}
              onClick={() => toggleAutoResume?.()}
              title="Marcador de leitura: ao abrir o capítulo, saltar automaticamente para a primeira página com falas pendentes"
            >
              <Bookmark size={11} />
              {autoResumePending && <div className="indicator-dot" />}
            </button>
          </div>
        )}
      </div>

      <div className="content-header-center">
        <div className="view-mode-selector">
          <div
            className={`view-mode-btn ${viewMode === "script" ? "active" : ""}`}
            onClick={() => changeViewMode?.("script")}
          >
            <FileText size={13} /><div>Roteiro</div>
          </div>
          <div
            className={`view-mode-btn ${viewMode === "split" ? "active" : ""}`}
            onClick={() => changeViewMode?.("split")}
          >
            <Columns size={13} /><div>Lado a Lado</div>
          </div>
          <div
            className={`view-mode-btn ${viewMode === "raw" ? "active" : ""}`}
            onClick={() => changeViewMode?.("raw")}
          >
            <AlignLeft size={13} /><div>Texto Puro</div>
          </div>
        </div>
      </div>

      <div className="content-header-right">

        {parsedPages.length > 0 && (
          <div className="chapter-search-wrap">
            <Search size={13} className="search-icon" />
            <input
              ref={searchInputRef}
              type="text"
              className={`chapter-search-input ${activeSearchQuery ? "has-term" : ""}`}
              placeholder={isMac ? "Localizar..." : "Localizar (Ctrl+F)..."}
              value={activeSearchQuery}
              onChange={(e) => setActiveSearchQuery?.(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  if (e.shiftKey) handlePrevSearchMatch?.();
                  else handleNextSearchMatch?.();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  clearSearch?.();
                  searchInputRef?.current?.blur();
                }
              }}
            />
            {activeSearchQuery && (
              <div className="search-nav-group">
                <div className="search-count">
                  {searchMatches.length > 0 ? `${currentMatchIndex + 1}/${searchMatches.length}` : "0/0"}
                </div>
                <button type="button" className="btn-search-nav" onClick={handlePrevSearchMatch}>
                  <ChevronLeft size={12} />
                </button>
                <button type="button" className="btn-search-nav" onClick={handleNextSearchMatch}>
                  <ChevronRight size={12} />
                </button>
                <button type="button" className="btn-search-nav" onClick={clearSearch}>
                  <X size={12} />
                </button>
              </div>
            )}
          </div>
        )}

        {viewMode === "split" && (
          <div className="split-tools-group">
            <button type="button" className="btn-split-tool primary-split-btn" onClick={() => copyFullPage?.(activePageData)}>
              <Copy size={12} /><div>Copiar Pág ({activePageData?.balloons?.length || 0})</div>
            </button>
            {activePageData?.pageName && (
              <button
                type="button"
                className="btn-split-tool studio-link"
                onClick={() => openInStudio?.(activePageData.pageName)}
                title="Abrir página no Estúdio"
              >
                <Edit3 size={12} /><div>Studio</div>
              </button>
            )}
            <div className="dropdown-wrapper">
              <button
                type="button"
                className={`btn-split-tool ${isExportMenuOpen ? "active" : ""}`}
                onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
                title="Exportar Roteiro"
              >
                <Download size={12} /><div>Exportar</div>
              </button>
              {isExportMenuOpen && (
                <div className="lib-dropdown-menu right">
                  <button
                    type="button"
                    className="dropdown-btn-action"
                    onClick={() => { setIsExportMenuOpen(false); exportScript?.("clean_txt"); }}
                  >
                    <FileText size={13} /> Roteiro Limpo (.txt)
                  </button>
                  <button
                    type="button"
                    className="dropdown-btn-action"
                    onClick={() => { setIsExportMenuOpen(false); exportScript?.("rtf"); }}
                  >
                    <FileText size={13} /> Formato Word (.rtf)
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {viewMode === "script" && (
          <div className="toolbar-actions-group">
            {syncChapterTxt && (
              <button
                type="button"
                className="btn-lib-cta secondary"
                onClick={syncChapterTxt}
                disabled={isSyncing}
                title="Sincronizar páginas do capítulo com o roteiro consolidado (.txt) da biblioteca"
              >
                <RefreshCw size={13} className={isSyncing ? "spin" : ""} />
                <div className="btn-cta-label">{isSyncing ? "Sincronizando..." : "Sincronizar .TXT"}</div>
              </button>
            )}
            <div className="dropdown-wrapper">
              <button
                type="button"
                className={`btn-lib-cta secondary ${isTypographyRulesOpen ? "menu-open" : ""}`}
                onClick={() => setIsTypographyRulesOpen(!isTypographyRulesOpen)}
                title="Regras de Tipografia ao Copiar"
              >
                {isTypographyRulesOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                <div className="btn-cta-label">Tipografia</div>
              </button>
              {isTypographyRulesOpen && (
                <div className="lib-dropdown-menu">
                  <div className="dropdown-title">Formatação ao Copiar</div>
                  <div className="dropdown-item">
                    <input
                      type="checkbox"
                      checked={typographyRules?.travessao ?? true}
                      onChange={(e) => updateTypographyRules?.({ travessao: e.target.checked })}
                    />
                    <div>Travessão (— em vez de -)</div>
                  </div>
                  <div className="dropdown-item">
                    <input
                      type="checkbox"
                      checked={typographyRules?.reticencias ?? true}
                      onChange={(e) => updateTypographyRules?.({ reticencias: e.target.checked })}
                    />
                    <div>Reticências tipográficas (…)</div>
                  </div>
                  <div className="dropdown-item">
                    <input
                      type="checkbox"
                      checked={typographyRules?.caixaAlta ?? false}
                      onChange={(e) => updateTypographyRules?.({ caixaAlta: e.target.checked })}
                    />
                    <div>FORÇAR CAIXA ALTA</div>
                  </div>
                </div>
              )}
            </div>

            <div className="dropdown-wrapper">
              <button
                type="button"
                className={`btn-lib-cta secondary ${isExportMenuOpen ? "menu-open" : ""}`}
                onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
                title="Exportar Roteiro"
              >
                <Download size={13} />
                <div className="btn-cta-label">Exportar</div>
              </button>
              {isExportMenuOpen && (
                <div className="lib-dropdown-menu right">
                  <button
                    type="button"
                    className="dropdown-btn-action"
                    onClick={() => { setIsExportMenuOpen(false); exportScript?.("clean_txt"); }}
                  >
                    <FileText size={13} /> Roteiro Limpo (.txt)
                  </button>
                  <button
                    type="button"
                    className="dropdown-btn-action"
                    onClick={() => { setIsExportMenuOpen(false); exportScript?.("rtf"); }}
                  >
                    <FileText size={13} /> Formato Word (.rtf)
                  </button>
                </div>
              )}
            </div>

            {parsedPages.length > 0 && (
              <button
                type="button"
                className="btn-lib-cta secondary"
                onClick={() => {
                  if (isAllExpanded) {
                    const collapsed = {};
                    parsedPages.forEach((p) => { collapsed[p.pageNumber] = true; });
                    setCollapsedPages?.(collapsed);
                  } else {
                    setCollapsedPages?.({});
                  }
                }}
                title={isAllExpanded ? "Recolher todas as páginas" : "Expandir todas as páginas"}
              >
                <ChevronsUpDown size={13} />
                <div className="btn-cta-label">{isAllExpanded ? "Recolher" : "Expandir"}</div>
              </button>
            )}

            <button type="button" className="btn-lib-cta primary" onClick={copyRawContent}>
              {isRawCopied ? <Check size={13} /> : <Copy size={13} />}
              <div className="btn-cta-label">{isRawCopied ? "Copiado!" : "Copiar Tudo"}</div>
            </button>
          </div>
        )}

        {viewMode === "raw" && (
          <div className="toolbar-actions-group">
            <button type="button" className="btn-lib-cta primary" onClick={copyRawContent}>
              {isRawCopied ? <Check size={13} /> : <Copy size={13} />}
              <div className="btn-cta-label">{isRawCopied ? "Copiado!" : "Copiar Tudo"}</div>
            </button>
          </div>
        )}
      </div>
    </div>
  );
});

export default LibraryHeader;
