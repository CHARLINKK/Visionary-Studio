import { useCallback, useEffect } from "react";
import { useLibraryStore, readTypographyRulesFromStorage } from "../stores/useLibraryStore";

/**
 * Hook para gerenciamento e aplicação de regras de tipografia/formatação de texto
 * copiadas para a área de transferência no fluxo de letreiramento.
 * Utiliza `useLibraryStore` como Fonte Única da Verdade (Single Source of Truth).
 */
export function useTypographyRules() {
  const typographyRules = useLibraryStore((state) => state.typographyRules);
  const updateTypographyRules = useLibraryStore((state) => state.updateTypographyRules);

  useEffect(() => {
    // Sincroniza caso o storage tenha sido populado externamente (testes ou persistência síncrona prévia)
    const stored = readTypographyRulesFromStorage();
    const current = useLibraryStore.getState().typographyRules;
    if (
      stored.travessao !== current.travessao ||
      stored.reticencias !== current.reticencias ||
      stored.caixaAlta !== current.caixaAlta
    ) {
      useLibraryStore.getState().initializeTypographyRules();
    }
  }, []);

  const applyTypographyRules = useCallback((text) => {
    if (!text || text === "[PENDENTE]") return text;
    let res = text;
    if (typographyRules.reticencias) res = res.replace(/\.{3,}/g, "…");
    if (typographyRules.travessao) res = res.replace(/^[-–—]{1,3}\s*/gm, "— ");
    if (typographyRules.caixaAlta) res = res.toUpperCase();
    return res;
  }, [typographyRules]);

  return {
    typographyRules,
    updateTypographyRules,
    applyTypographyRules,
  };
}
