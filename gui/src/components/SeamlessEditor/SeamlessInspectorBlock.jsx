import React from "react";
import {
  AlertCircle,
  CheckCircle,
  X,
  Trash2,
  GripVertical,
  RotateCcw,
} from "lucide-react";
import { normalizeInspectorBubble, reindexBubbleOrders } from "../../utils/bubbleNormalizer";

function removeBubbleAndReindex(boxes, targetId) {
  if (!Array.isArray(boxes)) return [];
  const targetGroup = boxes.find((x) => x.id === targetId)?.group_id;
  let filtered = boxes.filter((x) => x.id !== targetId);
  if (
    targetGroup &&
    filtered.filter((x) => x.group_id === targetGroup).length === 1
  ) {
    filtered = filtered.map((x) =>
      x.group_id === targetGroup ? { ...x, group_id: undefined } : x
    );
  }
  return reindexBubbleOrders(filtered);
}

const SeamlessInspectorBlock = React.memo(function SeamlessInspectorBlock({
  b,
  i,
  ocrData,
  setOcrData,
  activeBubbleId,
  setActiveBubbleId,
  viewMode,
  previewSrc,
  setPreviewSrc,
  zoomToSpecificBubble,
  debouncedHistoryUpdate,
  pushHistory,
  startHistoryTransaction,
  commitHistoryTransaction,
}) {
  const isSelected = activeBubbleId === b.id;
  const {
    text: ocrText,
    translated: translatedText,
    aiTranslated,
    isEdited,
    isDeleted,
    rawOcr,
    hasMoved,
  } = normalizeInspectorBubble(b);

  const handleRestorePosition = (e) => {
    e.stopPropagation();
    pushHistory(ocrData);
    const ibox = Array.isArray(b.initial_box) && b.initial_box.length === 4
      ? b.initial_box
      : [b.x1, b.y1, b.x2, b.y2];
    const ipoly = Array.isArray(b.initial_polygon) && b.initial_polygon.length > 0
      ? b.initial_polygon
      : b.polygon;
    debouncedHistoryUpdate(b.id, {
      x1: ibox[0],
      y1: ibox[1],
      x2: ibox[2],
      y2: ibox[3],
      polygon: ipoly ? JSON.parse(JSON.stringify(ipoly)) : b.polygon,
    });
  };

  const handleDeleteBlock = (e) => {
    e.stopPropagation();
    setOcrData((data) => {
      pushHistory(data);
      return {
        ...data,
        boxes: removeBubbleAndReindex(data?.boxes, b.id),
      };
    });
    if (isSelected) setActiveBubbleId(null);
  };

  return (
    <div
      key={b.id}
      id={`panel-block-${b.id}`}
      className={`inspector-block-card ${isSelected ? "active" : ""} ${
        isDeleted ? "warning-delete" : ""
      }`}
      draggable={true}
      onDragStart={(e) => {
        setPreviewSrc(b.id);
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", b.id);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
      }}
      onDrop={(e) => {
        e.preventDefault();
        if (previewSrc && previewSrc !== b.id) {
          setOcrData((data) => {
            pushHistory(data);
            const next = { ...data };
            if (next.boxes) {
              const arr = [...next.boxes];
              const i1 = arr.findIndex((x) => x.id === previewSrc);
              const i2 = arr.findIndex((x) => x.id === b.id);
              if (i1 > -1 && i2 > -1) {
                const [moved] = arr.splice(i1, 1);
                arr.splice(i2, 0, moved);
              }
              next.boxes = reindexBubbleOrders(arr);
            }
            return next;
          });
        }
        setPreviewSrc(null);
      }}
      onDragEnd={() => setPreviewSrc(null)}
      style={{ opacity: previewSrc === b.id ? 0.4 : 1 }}
      onClick={() => {
        if (activeBubbleId === b.id) {
          setActiveBubbleId(null);
        } else {
          setActiveBubbleId(b.id);
          zoomToSpecificBubble(b.id);
        }
      }}
    >
      <div className="inspector-block-header">
        <div className="inspector-block-title-group">
          <div
            className="inspector-block-grip"
            title="Arraste para reordenar"
          >
            <GripVertical
              size={15}
              color={
                isSelected ? "var(--brand-primary)" : "var(--text-muted)"
              }
            />
          </div>
          <span className="inspector-block-label">BLOCO #</span>
          <input
            type="number"
            min="1"
            max={(ocrData.boxes || []).length}
            value={i + 1}
            className="inspector-block-input"
            onChange={(e) => {
              let nextIdx = parseInt(e.target.value, 10) - 1;
              if (isNaN(nextIdx)) return;
              nextIdx = Math.max(
                0,
                Math.min(nextIdx, (ocrData.boxes || []).length - 1)
              );
              if (nextIdx !== i) {
                setOcrData((data) => {
                  pushHistory(data);
                  const next = { ...data };
                  if (next.boxes) {
                    const arr = [...next.boxes];
                    const idx = arr.findIndex((x) => x.id === b.id);
                    if (idx !== -1) {
                      const [moved] = arr.splice(idx, 1);
                      arr.splice(nextIdx, 0, moved);
                    }
                    next.boxes = reindexBubbleOrders(arr);
                  }
                  return next;
                });
              }
            }}
            onClick={(e) => e.stopPropagation()}
            title="Digite a nova posição para reordenar"
          />
        </div>
        <button
          type="button"
          className="inspector-block-remove-btn"
          onClick={handleDeleteBlock}
          title="Excluir este balão"
        >
          <X size={16} />
        </button>
      </div>

      {hasMoved && (
        <div className="inspector-block-restore-bar">
          <button
            type="button"
            className="inspector-btn-restore-pos"
            onClick={handleRestorePosition}
            title="Restaurar a posição e o contorno originais de detecção deste balão"
          >
            <RotateCcw size={12} />
            <span>Voltar ao local inicial</span>
          </button>
        </div>
      )}

      {isDeleted && (
        <div className="inspector-decision-card">
          <div className="inspector-decision-header">
            <AlertCircle size={14} color="#f59e0b" />
            <span>Sugerido para Descarte (Ruído / SFX)</span>
          </div>
          {rawOcr ? (
            <div className="inspector-decision-body">
              <span className="inspector-decision-label">
                Texto lido pelo OCR:
              </span>
              <div className="inspector-decision-ocr">"{rawOcr}"</div>
            </div>
          ) : (
            <div className="inspector-decision-body">
              <span className="inspector-decision-label">
                Nenhum texto alfanumérico detectado
              </span>
            </div>
          )}
          <div className="inspector-decision-actions">
            <button
              type="button"
              className="btn-decision-keep"
              onClick={(e) => {
                e.stopPropagation();
                pushHistory(ocrData);
                debouncedHistoryUpdate(b.id, {
                  text: rawOcr || "",
                  translated:
                    viewMode === "translation"
                      ? translatedText === "[DELETE]"
                        ? ""
                        : translatedText
                      : undefined,
                  is_sfx: false,
                  user_edited: true,
                });
              }}
              title="Restaurar a leitura original do OCR e preservar este balão na página"
            >
              <CheckCircle size={13} />
              {rawOcr ? `Manter "${rawOcr}"` : "Manter Balão"}
            </button>
            <button
              type="button"
              className="btn-decision-discard"
              onClick={handleDeleteBlock}
              title="Remover definitivamente este balão da página e do roteiro"
            >
              <Trash2 size={13} />
              Descartar
            </button>
          </div>
        </div>
      )}

      {viewMode === "translation" && (
        <div className="inspector-ref-box">
          <span className="inspector-ref-title">TEXTO ORIGINAL OCR:</span>
          {ocrText || <em>Vazio...</em>}
        </div>
      )}

      {viewMode === "translation" && aiTranslated && (
        <div className="inspector-debug-box">
          <div className="inspector-debug-header">
            <div
              className={`inspector-debug-title ${isEdited ? "edited" : ""}`}
            >
              {isEdited
                ? "⚠️ IA ORIGINAL (EDITADO MANUALMENTE):"
                : "🤖 IA ORIGINAL (DEBUG):"}
            </div>
            {isEdited && (
              <button
                type="button"
                className="inspector-btn-restore-ai"
                onClick={(e) => {
                  e.stopPropagation();
                  pushHistory(ocrData);
                  debouncedHistoryUpdate(b.id, {
                    translated: aiTranslated,
                    user_edited: false,
                  });
                }}
                title="Restaurar a tradução original gerada pela IA"
              >
                ↺ Restaurar IA
              </button>
            )}
          </div>
          <div className="inspector-debug-text">{aiTranslated}</div>
        </div>
      )}

      <textarea
        id={`textarea-${b.id}`}
        className="inspector-block-textarea"
        spellCheck={viewMode === "translation"}
        lang="pt-BR"
        value={
          viewMode === "ocr"
            ? ocrText === "[DELETE]"
              ? ""
              : ocrText
            : translatedText === "[DELETE]"
              ? ""
              : translatedText
        }
        placeholder={
          viewMode === "ocr"
            ? isDeleted
              ? "Texto sugerido para descarte (SFX / Ruído)..."
              : "Texto bruto OCR..."
            : "Tradução..."
        }
        onFocus={startHistoryTransaction}
        onBlur={commitHistoryTransaction}
        onClick={(e) => {
          e.stopPropagation();
          if (activeBubbleId !== b.id) {
            setActiveBubbleId(b.id);
            zoomToSpecificBubble(b.id);
          }
        }}
        onChange={(e) => {
          if (viewMode === "ocr") {
            debouncedHistoryUpdate(b.id, {
              text: e.target.value,
              is_sfx: false,
              user_edited: true,
            });
          } else if (viewMode === "translation") {
            const val = e.target.value;
            debouncedHistoryUpdate(b.id, {
              translated: val,
              user_edited: !aiTranslated || val.trim() !== aiTranslated.trim(),
            });
          }
        }}
      />
    </div>
  );
});

export default SeamlessInspectorBlock;
