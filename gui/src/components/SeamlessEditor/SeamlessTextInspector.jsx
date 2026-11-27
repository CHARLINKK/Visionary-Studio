import React from "react";
import SeamlessInspectorBlock from "./SeamlessInspectorBlock";

export default function SeamlessTextInspector(props) {
  const {
    viewMode,
    canEditLayout,
    canEditOcr,
    canEditTranslation,
    ocrData,
  } = props;

  return (
    <div className="inspector-text-container">
      <div className="inspector-section inspector-text-header">
        <h4 className="inspector-text-title">
          {viewMode === "ocr" ? "Extração OCR" : "Tradução"}
        </h4>
        {!canEditLayout && !canEditOcr && !canEditTranslation && (
          <div className="empty-state text-sm">Nenhum dado processado</div>
        )}
      </div>
      <div className="inspector-text-scroll">
        {(ocrData?.boxes || []).map((b, i) => (
          <SeamlessInspectorBlock key={b.id} b={b} i={i} {...props} />
        ))}
      </div>
    </div>
  );
}
