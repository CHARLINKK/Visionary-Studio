import React from "react";
import { FolderOpen, FileText } from "lucide-react";
import "./Library.css";

import LibrarySplitView from "./Library/LibrarySplitView";
import LibraryScriptView from "./Library/LibraryScriptView";
import LibraryRawTextViewer from "./Library/LibraryRawTextViewer";
import LibraryHeader from "./Library/LibraryHeader";
import { useLibraryController } from "../hooks/useLibraryController";

export default function Library({ activeChapterName, activeChapterPath, isActive = false }) {
  const ctrl = useLibraryController({ activeChapterName, activeChapterPath, isActive });

  return (
    <div className="library-container">
      <div className="library-content">
        {ctrl.activeFile ? (
          <React.Fragment>
            <LibraryHeader controller={ctrl} />

            <div className={`content-body ${ctrl.viewMode === "split" ? "is-split-mode" : ""}`}>
              <div key={ctrl.viewMode} className="view-mode-pane-container">
                {ctrl.isRawMode || ctrl.parsedPages.length === 0 ? (
                  <LibraryRawTextViewer
                    content={ctrl.fileContent}
                    onSelectBalloon={ctrl.jumpToBalloonInSplit}
                  />
                ) : ctrl.viewMode === "split" ? (
                  <LibrarySplitView
                    activeFile={ctrl.activeFile}
                    activePageData={ctrl.activePageData}
                    getPreviewUrl={ctrl.getPreviewUrl}
                    currentPageCards={ctrl.currentPageCards}
                    copyBalloon={ctrl.copyBalloon}
                    undoCopyBalloon={ctrl.undoCopyBalloon}
                    activeTab={ctrl.activeTab}
                    setActiveTab={ctrl.setActiveTab}
                    saveBalloonText={ctrl.saveBalloonText}
                    searchMatches={ctrl.searchMatches}
                    activeSearchMatchKey={ctrl.activeMatchKey}
                  />
                ) : (
                  <LibraryScriptView
                    parsedPages={ctrl.parsedPages}
                    collapsedPages={ctrl.collapsedPages}
                    setCollapsedPages={ctrl.setCollapsedPages}
                    activeTab={ctrl.activeTab}
                    setActiveTab={ctrl.setActiveTab}
                    copyBalloon={ctrl.copyBalloon}
                    undoCopyBalloon={ctrl.undoCopyBalloon}
                    saveBalloonText={ctrl.saveBalloonText}
                    copyFullPage={ctrl.copyFullPage}
                    setActivePageIndex={ctrl.setActivePageIndex}
                    setViewMode={ctrl.setViewMode}
                    openInStudio={ctrl.openInStudio}
                    searchMatches={ctrl.searchMatches}
                    activeSearchMatchKey={ctrl.activeMatchKey}
                    onJumpToSplit={ctrl.jumpToBalloonInSplit}
                  />
                )}
              </div>
            </div>
          </React.Fragment>
        ) : (
          <div className="library-placeholder">
            <div className="placeholder-icon-wrap"><FileText size={40} /></div>
            <div>Selecione um capítulo na lista para visualizar o roteiro de tradução.</div>
            <button type="button" className="btn-lib-cta secondary" onClick={ctrl.openLibraryFolder}>
              <FolderOpen size={14} /> Abrir Pasta dos Capítulos
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
