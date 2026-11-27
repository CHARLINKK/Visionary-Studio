import { useState, useEffect, useCallback, useMemo } from "react";

/**
 * Hook para busca textual no roteiro do capítulo (balões em PT e EN),
 * controle de ocorrências encontradas e navegação/scroll automático entre matches.
 */
export function useLibrarySearch({
  allBalloonsList = [],
  parsedPages = [],
  activePageIndex = 0,
  setActivePageIndex,
  viewMode = "script",
  setCollapsedPages,
}) {
  const [activeSearchQuery, setActiveSearchQuery] = useState("");
  const [searchMatches, setSearchMatches] = useState([]);
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);

  const scrollToMatch = useCallback((matchKey) => {
    if (!matchKey) return;
    const [pageStr] = matchKey.split("-");
    const pageNum = parseInt(pageStr, 10);
    const pageIdx = parsedPages.findIndex((p) => p.pageNumber === pageNum);

    if (pageIdx !== -1 && pageIdx !== activePageIndex && typeof setActivePageIndex === "function") {
      setActivePageIndex(pageIdx);
    }

    if (viewMode === "script" && typeof setCollapsedPages === "function" && pageNum) {
      setCollapsedPages((prev) => ({ ...prev, [pageNum]: false }));
    }

    setTimeout(() => {
      const elementId = viewMode === "split" ? `split-balloon-${matchKey}` : `balloon-${matchKey}`;
      document.getElementById(elementId)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }, 50);
  }, [parsedPages, activePageIndex, setActivePageIndex, viewMode, setCollapsedPages]);

  useEffect(() => {
    if (!activeSearchQuery.trim()) {
      setSearchMatches((prev) => (prev.length === 0 ? prev : []));
      setCurrentMatchIndex((prev) => (prev === 0 ? prev : 0));
      return;
    }

    const query = activeSearchQuery.toLowerCase();
    const matches = [];

    allBalloonsList.forEach((item) => {
      const brText = item.balloon?.br != null ? String(item.balloon.br).toLowerCase() : "";
      const enText = item.balloon?.en != null ? String(item.balloon.en).toLowerCase() : "";
      if ((brText && brText.includes(query)) || (enText && enText.includes(query))) {
        matches.push(item.key);
      }
    });

    setSearchMatches(matches);
    setCurrentMatchIndex(0);

    if (matches.length > 0) {
      scrollToMatch(matches[0]);
    }
  }, [activeSearchQuery, allBalloonsList, scrollToMatch]);

  const handleNextSearchMatch = useCallback(() => {
    if (searchMatches.length === 0) return;
    const nextIdx = (currentMatchIndex + 1) % searchMatches.length;
    setCurrentMatchIndex(nextIdx);
    scrollToMatch(searchMatches[nextIdx]);
  }, [searchMatches, currentMatchIndex, scrollToMatch]);

  const handlePrevSearchMatch = useCallback(() => {
    if (searchMatches.length === 0) return;
    const prevIdx = (currentMatchIndex - 1 + searchMatches.length) % searchMatches.length;
    setCurrentMatchIndex(prevIdx);
    scrollToMatch(searchMatches[prevIdx]);
  }, [searchMatches, currentMatchIndex, scrollToMatch]);

  const clearSearch = useCallback(() => {
    setActiveSearchQuery("");
    setSearchMatches([]);
    setCurrentMatchIndex(0);
  }, []);

  const activeMatchKey = useMemo(() => {
    return searchMatches[currentMatchIndex] || null;
  }, [searchMatches, currentMatchIndex]);

  return {
    activeSearchQuery,
    setActiveSearchQuery,
    searchMatches,
    currentMatchIndex,
    activeMatchKey,
    handleNextSearchMatch,
    handlePrevSearchMatch,
    clearSearch,
  };
}
