/**
 * Slice 5: Revisões Numéricas de Cache
 */
export const createRevisionSlice = (set) => ({
  workspaceRevision: 0,
  bumpWorkspaceRevision: () => set((state) => ({ workspaceRevision: state.workspaceRevision + 1 })),
  explorerRevision: 0,
  bumpExplorerRevision: () => set((state) => ({ explorerRevision: state.explorerRevision + 1 })),
  ollamaRevision: 0,
  bumpOllamaRevision: () => set((state) => ({ ollamaRevision: state.ollamaRevision + 1 })),
});
