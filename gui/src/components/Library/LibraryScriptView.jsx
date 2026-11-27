import React from "react";
import { ChevronDown, ChevronRight, FileText, Edit3, Copy, AlertTriangle } from "lucide-react";
import LibraryBalloonRow from "./LibraryBalloonRow";

export default function LibraryScriptView({
  parsedPages,
  collapsedPages,
  setCollapsedPages,
  activeTab,
  setActiveTab,
  copyBalloon,
  undoCopyBalloon,
  saveBalloonText,
  copyFullPage,
  setActivePageIndex,
  setViewMode,
  openInStudio,
  searchMatches = [],
  activeSearchMatchKey = null,
  onJumpToSplit,
}) {
  return (
    <div className="library-interactive-scroll">
      {parsedPages.map((pageData) => {
        const isExpanded = !collapsedPages[pageData.pageNumber];
        return (
          <div key={pageData.pageNumber} id={`page-card-${pageData.pageNumber}`} className="script-page-card">
            <div
              className="script-page-header"
              onClick={() => {
                setCollapsedPages((prev) => ({ ...prev, [pageData.pageNumber]: !prev[pageData.pageNumber] }));
              }}
              style={{
                cursor: "pointer",
                userSelect: "none",
              }}
              title="Clique para recolher/expandir balões desta página"
            >
              <div className="page-title-wrap">
                {isExpanded ? (
                  <ChevronDown
                    size={15}
                    style={{
                      color: "var(--text-muted)",
                      flexShrink: 0,
                    }}
                  />
                ) : (
                  <ChevronRight
                    size={15}
                    style={{
                      color: "var(--text-muted)",
                      flexShrink: 0,
                    }}
                  />
                )}
                <div className="page-pill">
                  {"PÁGINA "}
                  {pageData.pageNumber}
                </div>
                <div className="page-filename">{pageData.pageName}</div>
                <div className="page-balloon-count">
                  {pageData.balloons.length === 0
                    ? "(Sem falas)"
                    : `(${pageData.balloons.length} balões)`}
                </div>
              </div>
              <div
                className="page-actions-group"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  type="button"
                  className="btn-open-split-view"
                  onClick={() => {
                    const idx = parsedPages.findIndex(
                      (p) => p.pageNumber === pageData.pageNumber,
                    );
                    if (idx !== -1) setActivePageIndex(idx);
                    setViewMode("split");
                  }}
                  title="Abrir visualização lado a lado com a imagem desta página"
                >
                  <FileText size={12} />
                  {" Lado a Lado"}
                </button>
                <button
                  type="button"
                  className="btn-open-studio"
                  onClick={() => openInStudio(pageData.pageName)}
                  title="Abrir esta página no Studio para edição ou inspeção"
                >
                  <Edit3 size={12} />
                  {" Studio"}
                </button>
                <button
                  type="button"
                  className="btn-copy-page"
                  onClick={() => copyFullPage(pageData)}
                  disabled={pageData.balloons.length === 0}
                  title={
                    pageData.balloons.length === 0
                      ? "Página sem falas para copiar"
                      : "Copiar todos os balões desta página para o Photoshop"
                  }
                >
                  <Copy size={12} />
                  {" Copiar Página"}
                </button>
              </div>
            </div>
            {isExpanded && (
              <div className="script-balloons-list">
                {pageData.balloons.length === 0 ? (
                  <div className="empty-page-notice">
                    <AlertTriangle size={13} />
                    <div>Página sem falas ou diálogos detectados</div>
                  </div>
                ) : (
                  pageData.balloons.map((balloon, idx) => {
                    const rowKey = `${pageData.pageNumber}-${idx}`;
                    return (
                      <LibraryBalloonRow
                        key={rowKey}
                        pageData={pageData}
                        balloonData={balloon}
                        bIdx={idx}
                        isSplitMode={false}
                        activeTab={activeTab}
                        setActiveTab={setActiveTab}
                        isSearchMatch={searchMatches.includes(rowKey)}
                        isSearchActive={activeSearchMatchKey === rowKey}
                        copyBalloon={copyBalloon}
                        undoCopyBalloon={undoCopyBalloon}
                        saveBalloonText={saveBalloonText}
                        onJumpToSplit={onJumpToSplit}
                      />
                    );
                  })
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
