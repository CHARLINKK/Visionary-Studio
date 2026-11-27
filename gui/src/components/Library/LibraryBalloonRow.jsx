import React, { useRef, useEffect } from "react";
import { Edit3, RotateCcw, Copy, Check, X } from "lucide-react";
import { useLibraryStore } from "../../stores/useLibraryStore";
import { useLibraryViewerStore } from "../../stores/useLibraryViewerStore";

export default function LibraryBalloonRow({
  pageData,
  balloonData,
  bIdx,
  isSplitMode = false,
  activeTab,
  setActiveTab,
  isSearchMatch,
  isSearchActive,
  copyBalloon,
  undoCopyBalloon,
  saveBalloonText,
  currentPageCard,
  onJumpToSplit,
}) {
  const key = `${pageData.pageNumber}-${bIdx}`;

  const copiedBlocks = useLibraryStore((s) => s.copiedBlocks);
  const activeCopiedId = useLibraryStore((s) => s.activeCopiedId);
  const setActiveCopiedId = useLibraryStore((s) => s.setActiveCopiedId);

  const activeBlockId = useLibraryViewerStore((s) => s.activeBlockId);
  const setActiveBlockId = useLibraryViewerStore((s) => s.setActiveBlockId);
  const hideEnglish = useLibraryViewerStore((s) => s.hideEnglish);
  const setZoomTargetRect = useLibraryViewerStore((s) => s.setZoomTargetRect);

  const isCopied = !!copiedBlocks[key];
  const isFocused = activeCopiedId === key;
  const isHovered = activeBlockId === bIdx;
  const isEditing = activeTab?.key === key;

  const inputRef = useRef(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      try {
        const range = document.createRange();
        range.selectNodeContents(inputRef.current);
        range.collapse(false);
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);
      } catch (_) {}
    }
  }, [isEditing]);

  return (
    <div
      id={isSplitMode ? `split-balloon-${key}` : `balloon-${key}`}
      className={`script-balloon-row ${isSplitMode ? "split-dense" : ""} ${isCopied ? "copied" : ""} ${balloonData.isPending ? "pending" : ""} ${isFocused ? "focused" : ""} ${isHovered ? "hovered" : ""} ${isSearchActive ? "search-active" : isSearchMatch ? "search-match" : ""}`}
      onClick={() => {
        if (!isEditing) {
          copyBalloon(key, balloonData);
          setActiveCopiedId(key);
          if (isSplitMode && currentPageCard) {
            setZoomTargetRect(currentPageCard);
          }
        }
      }}
      onMouseEnter={() => setActiveBlockId(bIdx)}
      onMouseLeave={() => setActiveBlockId(null)}
      title={isEditing ? "" : "Clique para copiar • Duplo clique para editar"}
    >
      <div
        className={`balloon-num-badge ${!isSplitMode ? "clickable-jump" : ""}`}
        onClick={(e) => {
          if (!isSplitMode && onJumpToSplit) {
            e.stopPropagation();
            onJumpToSplit(pageData.pageNumber, bIdx, balloonData?.id);
          }
        }}
        title={!isSplitMode ? `Abrir Pág. ${pageData.pageNumber}, Balão #${bIdx + 1} no modo Lado a Lado` : `Balão #${bIdx + 1}`}
      >
        <div>
          {"#"}
          {bIdx + 1}
        </div>
        {!isSplitMode && <span className="badge-jump-icon">↗</span>}
      </div>
      <div className="balloon-text-col">
        {(!isSplitMode || !hideEnglish) && balloonData.en && (
          <div className="balloon-en-line">
            <div className="lang-tag en">EN:</div>
            <div className="text-val">{balloonData.en}</div>
          </div>
        )}
        {isEditing ? (
          <div className="balloon-edit-form" onClick={(e) => e.stopPropagation()}>
            <div
              contentEditable={true}
              ref={inputRef}
              className="balloon-edit-input"
              suppressContentEditableWarning={true}
              onBlur={(e) => {
                const currentText = e.currentTarget.innerText;
                setActiveTab((prev) => (prev && prev.key === key ? { ...prev, text: currentText } : prev));
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  saveBalloonText(pageData.pageNumber, bIdx, e.currentTarget.innerText);
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  setActiveTab(null);
                }
              }}
            >
              {activeTab.text}
            </div>
            <div className="balloon-edit-actions">
              <div
                className="btn-edit-save"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => saveBalloonText(pageData.pageNumber, bIdx, inputRef.current?.innerText || "")}
                title="Salvar alterações no arquivo .txt"
              >
                <Check size={12} />
                {" Salvar"}
              </div>
              <div
                className="btn-edit-cancel"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => setActiveTab(null)}
                title="Cancelar"
              >
                <X size={12} />
              </div>
            </div>
          </div>
        ) : (
          <div
            className="balloon-br-line"
            onDoubleClick={(e) => {
              e.stopPropagation();
              setActiveTab({
                key: key,
                pageNumber: pageData.pageNumber,
                bIdx: bIdx,
                text: balloonData.br === "[PENDENTE]" ? "" : balloonData.br,
              });
            }}
          >
            <div className="lang-tag br">
              {balloonData.typeTag ? `BR (${balloonData.typeTag}):` : "BR:"}
            </div>
            {balloonData.isPending ? (
              <div className="pending-tag">⏳ Tradução Pendente</div>
            ) : (
              <div className="text-val br-highlight">{balloonData.br}</div>
            )}
          </div>
        )}
      </div>
      <div className="balloon-action-col" onClick={(e) => e.stopPropagation()}>
        {!isEditing && (
          <div
            className="btn-edit-balloon"
            onClick={() =>
              setActiveTab({
                key: key,
                pageNumber: pageData.pageNumber,
                bIdx: bIdx,
                text: balloonData.br === "[PENDENTE]" ? "" : balloonData.br,
              })
            }
            title="Editar fala diretamente no roteiro"
          >
            <Edit3 size={12} />
          </div>
        )}
        {isCopied ? (
          <div className="copied-badge-pill">
            <button
              type="button"
              className="copied-badge-main"
              onClick={(e) => {
                e.stopPropagation();
                copyBalloon(key, balloonData);
                setActiveCopiedId(key);
              }}
              title="Já copiado para o Photoshop • Clique para copiar novamente"
            >
              <Check size={12} />
              {" Colado"}
            </button>
            <button
              type="button"
              className="btn-unmark-copied"
              onClick={(e) => {
                e.stopPropagation();
                undoCopyBalloon(key, e);
              }}
              title="Desmarcar cópia (definir como pendente)"
            >
              <RotateCcw size={11} />
            </button>
          </div>
        ) : (
          <div
            className="btn-quick-copy"
            onClick={(e) => {
              e.stopPropagation();
              copyBalloon(key, balloonData);
              setActiveCopiedId(key);
            }}
            title="Copiar balão para o Photoshop (Espaço ou clique)"
          >
            <Copy size={13} />
          </div>
        )}
      </div>
    </div>
  );
}
