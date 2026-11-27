import React, { useMemo } from "react";
import "./LibraryRawTextViewer.css";

function renderHighlightedLine(line, pageNumber, onSelectBalloon) {
  const trimmed = line.trim();

  // Empty line
  if (!trimmed) {
    return <span className="raw-line empty-line">&nbsp;</span>;
  }

  // Divider lines (====, ----, ####)
  if (/^[=\-#]{5,}$/.test(trimmed)) {
    return <span className="token-divider">{line}</span>;
  }

  // Header / Metadata comments
  if (trimmed.startsWith("#")) {
    if (trimmed.includes("VISIONARY STUDIO")) {
      return (
        <span className="raw-line">
          <span className="token-comment-hash"># </span>
          <span className="token-brand-title">{trimmed.replace(/^#\s*/, "")}</span>
        </span>
      );
    }
    if (trimmed.startsWith("# CAPITULO:")) {
      return (
        <span className="raw-line">
          <span className="token-comment-hash"># </span>
          <span className="token-meta-label">CAPITULO: </span>
          <span className="token-meta-val">{trimmed.replace(/^#\s*CAPITULO:\s*/, "")}</span>
        </span>
      );
    }
    if (trimmed.startsWith("# ATUALIZADO EM:")) {
      return (
        <span className="raw-line">
          <span className="token-comment-hash"># </span>
          <span className="token-meta-label">ATUALIZADO EM: </span>
          <span className="token-meta-val">{trimmed.replace(/^#\s*ATUALIZADO EM:\s*/, "")}</span>
        </span>
      );
    }
    if (trimmed.startsWith("# PROGRESSO:")) {
      return (
        <span className="raw-line">
          <span className="token-comment-hash"># </span>
          <span className="token-meta-label">PROGRESSO: </span>
          <span className="token-meta-progress">{trimmed.replace(/^#\s*PROGRESSO:\s*/, "")}</span>
        </span>
      );
    }

    // Balloon ID comment: # [id: 1] -> Minimalist clickable ID link
    const idMatch = trimmed.match(/^(#\s*)(\[(?:id|b):?\s*([^\]]+)\])(.*)$/i);
    if (idMatch) {
      const hashPart = idMatch[1];
      const tagText = idMatch[2];
      const balloonId = idMatch[3].trim();
      const rest = idMatch[4] || "";
      return (
        <span className="raw-line">
          <span className="token-comment-hash">{hashPart}</span>
          <span
            className="token-id-link"
            onClick={() => onSelectBalloon?.(pageNumber, balloonId)}
            title={`Abrir Pág. ${pageNumber || "?"}, Balão #${balloonId} no modo Lado a Lado`}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelectBalloon?.(pageNumber, balloonId);
              }
            }}
          >
            {tagText}
          </span>
          {rest && <span className="token-comment">{rest}</span>}
        </span>
      );
    }

    return <span className="token-comment">{line}</span>;
  }

  // Page title: PAGINA 1: 001.JPG
  const pageMatch = trimmed.match(/^(?:P[ÁAáa\ufffd?]?GINA|PAGE)\s*(\d+)(.*)$/i);
  if (pageMatch) {
    const pageNum = parseInt(pageMatch[1], 10);
    return (
      <span className="raw-line">
        <span className="token-page-label">{pageMatch[0].split(":")[0] || `PÁGINA ${pageNum}`}</span>
        <span className="token-page-file">{pageMatch[2]}</span>
      </span>
    );
  }

  // English line: [EN]: ...
  if (trimmed.startsWith("[EN]:") || trimmed.startsWith("[EN]")) {
    const textPart = trimmed.replace(/^\[EN\]:?\s*/, "");
    const isNoOcr = textPart.includes("Sem texto original detectado");
    return (
      <span className="raw-line">
        <span className="token-tag-en">[EN]:</span>{" "}
        <span className={isNoOcr ? "token-text-no-ocr" : "token-text-en"}>{textPart}</span>
      </span>
    );
  }

  // Portuguese line: [BR]: ...
  if (
    trimmed.startsWith("[BR]:") ||
    trimmed.startsWith("[BR]") ||
    trimmed.startsWith("[PT]:") ||
    trimmed.startsWith("[PT]")
  ) {
    const tagMatch = trimmed.match(/^(\[(?:BR|PT)\]:?)\s*(.*)$/);
    const tag = tagMatch ? tagMatch[1] : "[BR]:";
    const textPart = tagMatch ? tagMatch[2] : trimmed.replace(/^\[(?:BR|PT)\]:?\s*/, "");
    const isPending = textPart.includes("[PENDENTE]");
    return (
      <span className="raw-line">
        <span className="token-tag-br">{tag}</span>{" "}
        <span className={isPending ? "token-text-pending" : "token-text-br"}>{textPart}</span>
      </span>
    );
  }

  // Default fallback line
  return <span className="default-line">{line}</span>;
}

export const LibraryRawTextViewer = React.memo(function LibraryRawTextViewer({ content, onSelectBalloon }) {
  const parsedLines = useMemo(() => {
    if (!content) return [];
    const rawLines = content.split(/\r?\n/);
    let currentPageNumber = 1;
    return rawLines.map((line) => {
      const trimmed = line.trim();
      const pageMatch = trimmed
        .replace(/^[\s=\-#]+|[\s=\-#]+$/g, "")
        .trim()
        .match(/^(?:P[ÁAáa\ufffd?]?GINA|PAGE)\s*(\d+)/i);
      if (pageMatch) {
        currentPageNumber = parseInt(pageMatch[1], 10);
      }
      return {
        text: line,
        pageNumber: currentPageNumber,
      };
    });
  }, [content]);

  if (!content) {
    return <div className="raw-text-empty">Nenhum conteúdo disponível.</div>;
  }

  return (
    <div className="raw-syntax-container">
      <div className="raw-syntax-code">
        {parsedLines.map((item, idx) => (
          <div key={idx} className="raw-syntax-row">
            <span className="raw-line-num">{idx + 1}</span>
            <div className="raw-line-content">
              {renderHighlightedLine(item.text, item.pageNumber, onSelectBalloon)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});

export default LibraryRawTextViewer;
