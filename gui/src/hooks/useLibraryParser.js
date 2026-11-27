import { useMemo } from "react";

export function useLibraryParser(fileContent, activePageIndex) {
  // [PARSER BILINGUE] (O coração da extração de roteiro)
  // Transforma a string massiva de 10 mil linhas (fileContent) em um array de objetos estruturados.
  // Ele procura por cabeçalhos (PÁGINA X) e extrai pares de [EN] e [BR].
  const parsedPages = useMemo(() => {
    if (!fileContent || fileContent.startsWith("[ERRO]") || fileContent === "Carregando...") return [];
    let lines = fileContent.split("\n"),
      pages = [],
      currentPage = null,
      lastEnText = null,
      lastBalloonId = null,
      activeField = null;

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();
      if (!line || line.startsWith("===") || line.startsWith("---")) {
        activeField = null;
        continue;
      }

      let idMatch = line.match(/^(?:#\s*\[(?:id|b):?\s*([^\]]+)\]|<!--\s*id:\s*([^>]+)\s*-->)/i);
      if (idMatch) {
        lastBalloonId = (idMatch[1] || idMatch[2]).trim();
        activeField = null;
        continue;
      }

      if (line.startsWith("#") && !/(?:P[ÁAáa\ufffd?]?GINA|PAGE)\s*\d+/i.test(line)) {
        activeField = null;
        continue;
      }

      let pageMatch = line
        .replace(/^[\s=\-#]+|[\s=\-#]+$/g, "")
        .trim()
        .match(/^(?:P[ÁAáa\ufffd?]?GINA|PAGE)\s*(\d+)(?:[:\s-]+(.*))?$/i);

      if (pageMatch) {
        if (currentPage) pages.push(currentPage);
        currentPage = {
          pageNumber: parseInt(pageMatch[1], 10),
          pageName: (pageMatch[2] || "").trim() || `Página ${pageMatch[1]}`,
          balloons: [],
        };
        lastEnText = null;
        lastBalloonId = null;
        activeField = null;
        continue;
      }

      if (currentPage) {
        if (line.startsWith("[EN]:") || line.startsWith("[EN]")) {
          lastEnText = line.replace(/^\[EN\]:?\s*/i, "").trim();
          activeField = "en";
        } else if (line.startsWith("[BR]") || line.startsWith("[PT]")) {
          let match = line.match(/^\[(?:BR|PT)\](?:\s*\(([^)]+)\))?:\s*(.*)$/i),
            typeTag = "",
            text = "";
          if (match) {
            typeTag = match[1] || "";
            text = match[2] || "";
          } else {
            text = line.replace(/^\[(?:BR|PT)\]:?\s*/i, "");
          }
          let isPending = !text.trim() || text.trim() === "[PENDENTE]";
          currentPage.balloons.push({
            id: lastBalloonId || null,
            en: lastEnText || "",
            br: isPending ? "[PENDENTE]" : text.trim(),
            typeTag: typeTag,
            isPending: isPending,
            lineIndex: i,
            endLineIndex: i,
          });
          lastEnText = null;
          lastBalloonId = null;
          activeField = "br";
        } else if (line.match(/^\[?\d+[\].:]\s*(.*)$/)) {
          let match = line.match(/^\[?\d+[\].:]\s*(.*)$/),
            rawText = match ? match[1].trim() : line,
            typeTag = "",
            text = rawText,
            tagMatch = rawText.match(/^\(([^)]+)\)\s*(.*)$/);

          if (tagMatch) {
            typeTag = tagMatch[1];
            text = tagMatch[2];
          }
          let isPending = !text.trim() || text.trim() === "[PENDENTE]";
          currentPage.balloons.push({
            id: lastBalloonId || null,
            en: lastEnText || "",
            br: isPending ? "[PENDENTE]" : text.trim(),
            typeTag: typeTag,
            isPending: isPending,
            lineIndex: i,
            endLineIndex: i,
          });
          lastEnText = null;
          lastBalloonId = null;
          activeField = "br";
        } else if (activeField === "en") {
          lastEnText = lastEnText ? `${lastEnText}\n${line}` : line;
        } else if (activeField === "br" && currentPage.balloons.length > 0) {
          let prevBalloon = currentPage.balloons[currentPage.balloons.length - 1];
          let prevBr = prevBalloon.isPending ? "" : prevBalloon.br;
          let combined = prevBr ? `${prevBr}\n${line}` : line;
          prevBalloon.br = combined;
          prevBalloon.isPending = !combined.trim() || combined.trim() === "[PENDENTE]";
          prevBalloon.endLineIndex = i;
        }
      }
    }
    if (currentPage) pages.push(currentPage);
    return pages;
  }, [fileContent]);

  const activePageData = useMemo(() => {
    if (!parsedPages || parsedPages.length === 0) return null;
    let idx = Math.min(Math.max(0, activePageIndex), parsedPages.length - 1);
    return parsedPages[idx] || null;
  }, [parsedPages, activePageIndex]);

  const allBalloonsList = useMemo(() => {
    let list = [];
    parsedPages.forEach((page) => {
      page.balloons.forEach((balloon, idx) => {
        list.push({
          key: `${page.pageNumber}-${idx}`,
          pageNumber: page.pageNumber,
          bIdx: idx,
          balloon: balloon,
          pageName: page.pageName,
        });
      });
    });
    return list;
  }, [parsedPages]);

  return { parsedPages, activePageData, allBalloonsList };
}
