import { useCallback, useMemo } from "react";
import { useWorkspaceStore } from "../stores/useWorkspaceStore";
import { clientApi } from "../api/bridge";

export function useSeamlessBackend({
  page,
  chapterPath,
  ocrDataRef,
  hasBoxesRef,
  setSaveStatus,
  setIsSyncing,
  addToast,
}) {
  const pagePath = page?.path;

  const savePageLayout = useCallback(
    async (silent = false) => {
      const isClearing = useWorkspaceStore.getState().isClearingData;
      const currentBoxes = ocrDataRef?.current?.boxes;
      if (!isClearing && currentBoxes && pagePath) {
        setSaveStatus("saving");
        try {
          const validBoxes = currentBoxes.filter(Boolean);
          const res = await clientApi.save_page_layout(
            pagePath,
            validBoxes
          );
          if (res?.success) {
            setSaveStatus("saved");
            if (validBoxes.length === 0 && hasBoxesRef) hasBoxesRef.current = false;
            if (!silent) addToast("Layout salvo com sucesso!", "success");
          } else {
            setSaveStatus("error");
            if (!silent)
              addToast("Erro ao salvar layout: " + res?.error, "error");
          }
        } catch (t) {
          setSaveStatus("error");
          if (!silent)
            addToast("Erro ao salvar layout: " + (t?.message || t), "error");
        }
      }
    },
    [pagePath, ocrDataRef, setSaveStatus, hasBoxesRef, addToast]
  );

  const forceSyncChapterTxt = useCallback(async () => {
    setIsSyncing(true);
    try {
      const currentBoxes = ocrDataRef?.current?.boxes;
      if (currentBoxes && pagePath) {
        const validBoxes = currentBoxes.filter(Boolean);
        const saveRes = await clientApi.save_page_layout(pagePath, validBoxes);
        if (saveRes?.success) setSaveStatus("saved");
      }
      const targetPath = pagePath || chapterPath;
      if (targetPath) {
        const res = await clientApi.syncChapterTxt(targetPath);
        if (res && res.success) {
          addToast("Sincronizado com .txt", "success");
        } else {
          addToast("Falha ao sincronizar", "error");
        }
      }
    } catch {
      addToast("Erro ao sincronizar txt", "error");
    }
    setIsSyncing(false);
  }, [pagePath, chapterPath, ocrDataRef, setIsSyncing, setSaveStatus, addToast]);

  return useMemo(() => ({
    savePageLayout,
    forceSyncChapterTxt,
  }), [savePageLayout, forceSyncChapterTxt]);
}
