import React from "react";
import {
  SeamlessProvider,
  useSeamlessDoc,
  useSeamlessUi,
} from "../contexts/SeamlessContext";
import { useWorkspaceStore } from "../stores/useWorkspaceStore";
import { clientApi } from "../api/bridge";
import "./SeamlessEditor.css";
import ConfirmModal from "./ConfirmModal";
import SeamlessTopbar from "./SeamlessEditor/SeamlessTopbar";
import SeamlessCanvas from "./SeamlessCanvas";
import SeamlessSidebar from "./SeamlessEditor/SeamlessSidebar";
import CanvasErrorBoundary from "./CanvasErrorBoundary";

/**
 * Tela principal de edição de página do Studio (barra superior, canvas Konva e inspetor lateral).
 */
function SeamlessEditorContent() {
  const {
    page,
    setIsViewOnlyMode,
    setSaveStatus,
    setViewMode,
    setActiveBubbleId,
    setOcrData,
    setOcrDataRaw,
    history,
  } = useSeamlessDoc();

  const {
    isRestartModalOpen,
    setIsRestartModalOpen,
    addToast,
  } = useSeamlessUi();

  const { clearHistory } = history || {};

  return (
    <div className="seamless-editor fade-in-tab">
      <SeamlessTopbar />

      <div className="editor-workspace">
        <CanvasErrorBoundary resetKeys={[page?.path]}>
          <SeamlessCanvas />
        </CanvasErrorBoundary>
        <SeamlessSidebar />
      </div>

      <ConfirmModal
        isOpen={isRestartModalOpen}
        title="Recomeçar Página?"
        message="Deseja remover todos os balões e textos desta página e recomeçar do zero? A imagem original permanecerá intacta."
        confirmText="Recomeçar"
        onConfirm={async () => {
          setIsRestartModalOpen(false);
          const store = useWorkspaceStore.getState();
          store.setIsClearingData(true);
          clearHistory();
          if (setOcrDataRaw) {
            setOcrDataRaw({ boxes: [], panels: [] });
          } else {
            setOcrData({ boxes: [], panels: [] });
          }
          setSaveStatus("saved");
          setActiveBubbleId(null);
          setViewMode("view");
          setIsViewOnlyMode(true);
          try {
            const res = await clientApi.clearPageData(
              [page?.path],
              ["layout", "ocr", "translate", "translation"],
            );
            if (res && res.success) {
              addToast("Dados da página apagados com sucesso.", "success");
              store.bumpWorkspaceRevision();
              store.bumpExplorerRevision();
            } else {
              addToast("Erro ao apagar dados da página: " + (res?.error || "Desconhecido"), "error");
            }
          } catch (e) {
            addToast("Exceção ao apagar dados da página: " + (e?.message || String(e)), "error");
          } finally {
            store.setIsClearingData(false);
          }
        }}
        onClose={() => setIsRestartModalOpen(false)}
      />
    </div>
  );
}

export default function SeamlessEditor(props) {
  return (
    <SeamlessProvider {...props}>
      <SeamlessEditorContent onClose={props.onClose} />
    </SeamlessProvider>
  );
}
