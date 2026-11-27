import { useState, useRef } from "react";
import { sendNativeNotification } from "../utils/notification";
import { useWorkspaceStore } from "../stores/useWorkspaceStore";
import { clientApi } from "../api/bridge";

export function useLibraryBackend({
  activeFile,
  setActiveFile,
  fileContent,
  setFileContent,
  parsedPages,
  setBlockInputs,
  setActiveTab,
  addToast,
  refreshLibrary
}) {
  const [isSyncing, setIsSyncing] = useState(false);

  const syncChapterTxt = async () => {
    if (!activeFile) return;
    setIsSyncing(true);
    try {
      const target = activeFile.chapter_dir || activeFile.path;
      const res = await clientApi.syncChapterTxt(target);
      if (res && res.success) {
        addToast("Roteiro (.txt) sincronizado com sucesso!", "success");
        const contentRes = await clientApi.readLibraryFile(activeFile.path);
        if (contentRes && contentRes.content) {
          setFileContent(contentRes.content);
        }
        if (refreshLibrary) await refreshLibrary();
        useWorkspaceStore.getState().bumpWorkspaceRevision();
      } else {
        addToast("Erro ao sincronizar: " + (res?.error || "Desconhecido"), "error");
      }
    } catch (err) {
      addToast("Falha na sincronização: " + err.message, "error");
    } finally {
      setIsSyncing(false);
    }
  };

  const openInStudio = (pageName) => {
    if (!activeFile) return;
    if (pageName && /^P[ÁAáa\ufffd?]?GINA\s*\d+$/i.test(String(pageName).trim())) {
      addToast?.("Não é possível abrir no Studio: o cabeçalho desta página não contém o nome do arquivo de imagem.", "warning");
      return;
    }
    let folderPath = activeFile.chapter_dir || activeFile.path.replace(/[\\/][^\\/]+$/, "");
    let folderName = folderPath.replace(/^.*[\\/]/, "") || activeFile.name.replace(/\.txt$/i, "");

    useWorkspaceStore.getState().navigateToStudioPage({
      folderPath,
      folderName,
      pageName
    });
    addToast(`Abrindo ${pageName} no Studio...`, `info`);
  };

  const exportScript = async (format) => {
    if (activeFile) {
      try {
        let res = await clientApi.exportScript(activeFile.path, format);
        if (res && res.success) {
          let mime = format === `rtf` ? `application/rtf` : `text/plain;charset=utf-8`,
              blob = new Blob([res.content], { type: mime }),
              url = URL.createObjectURL(blob),
              a = document.createElement(`a`);
          a.href = url;
          a.download = res.filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          sendNativeNotification(`Visionary Studio // Exportação`, `Roteiro ${res.filename} exportado com sucesso!`);
          addToast(`Arquivo ${res.filename} exportado com sucesso!`, `success`);
        } else {
          addToast(`Erro ao exportar: ` + (res?.error || `falha desconhecida`), `error`);
        }
      } catch (err) {
        addToast(`Erro ao exportar roteiro: ` + err.message, `error`);
      }
    }
  };

  const deletePendingRef = useRef(null);
  const deleteTimerRef = useRef(null);

  const deleteLibraryFile = async (e, file) => {
    if (e && typeof e.stopPropagation === "function") e.stopPropagation();
    if (!file) return;

    if (deletePendingRef.current !== file.path) {
      deletePendingRef.current = file.path;
      addToast?.(`Clique novamente na lixeira para confirmar a exclusão de "${file.name}".`, "warning");
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
      deleteTimerRef.current = setTimeout(() => {
        if (deletePendingRef.current === file.path) deletePendingRef.current = null;
      }, 4000);
      return;
    }

    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    deletePendingRef.current = null;

    try {
      const res = await clientApi.deleteLibraryFile(file.path);
      if (res && res.success !== false) {
        addToast?.(`Arquivo "${file.name}" excluído!`, "info");
        if (activeFile?.path === file.path) {
          if (typeof setActiveFile === "function") setActiveFile(null);
          if (typeof setFileContent === "function") setFileContent("");
          try { localStorage.removeItem("visionary:cached_lib_active_file"); } catch (_) {}
        }
        if (refreshLibrary) await refreshLibrary();
        useWorkspaceStore.getState().bumpExplorerRevision();
      } else {
        addToast?.(`Erro ao excluir: ${res?.error || "Desconhecido"}`, "error");
      }
    } catch (err) {
      addToast?.(`Falha ao excluir arquivo: ${err.message}`, "error");
    }
  };

  const saveBalloonText = async (pageNum, bIdx, newText) => {
    if (!activeFile) return;
    let page = parsedPages.find((p) => p.pageNumber === pageNum);
    if (!page || !page.balloons[bIdx]) return;
    
    let balloon = page.balloons[bIdx],
        trimmedText = (newText || ``).trim(),
        lines = fileContent.split(`\n`),
        targetLine = lines[balloon.lineIndex];
        
    if (targetLine !== undefined) {
      let updatedLine;
      if (targetLine.match(/^\[(?:BR|PT)\]/i)) {
        let prefix = balloon.typeTag ? `[BR] (${balloon.typeTag}): ` : `[BR]: `;
        updatedLine = `${prefix}${trimmedText || `[PENDENTE]`}`;
      } else if (targetLine.match(/^\[\d+\]:?/)) {
        let match = targetLine.match(/^(\[\d+\]:?\s*)/),
            numPrefix = match ? match[1] : `[${bIdx + 1}]: `,
            tagPrefix = balloon.typeTag ? `(${balloon.typeTag}) ` : ``;
        updatedLine = `${numPrefix}${tagPrefix}${trimmedText || `[PENDENTE]`}`;
      } else {
        updatedLine = `[BR]: ${trimmedText || `[PENDENTE]`}`;
      }
      let endIdx = typeof balloon.endLineIndex === `number` && balloon.endLineIndex >= balloon.lineIndex
        ? balloon.endLineIndex
        : balloon.lineIndex;
      lines.splice(balloon.lineIndex, endIdx - balloon.lineIndex + 1, updatedLine);
      setFileContent(lines.join(`\n`));
    }
    setActiveTab(null);
    
    try {
      try {
        let res = await clientApi.updateBalloonText(activeFile.path, page.pageName, bIdx, trimmedText, balloon.en, balloon.id);
        if (res && res.success) {
          if (res.content) setFileContent(res.content);
          setBlockInputs((prev) => {
            let pName = page.pageName;
            if (!prev[pName]) return prev;
            let nextArr = [...prev[pName]];
            const cardIdx =
              balloon.id != null
                ? nextArr.findIndex((c) => c.id != null && String(c.id) === String(balloon.id))
                : bIdx;
            const targetIdx = cardIdx !== -1 ? cardIdx : bIdx;
            if (nextArr[targetIdx]) {
              nextArr[targetIdx] = {
                ...nextArr[targetIdx],
                translated: trimmedText,
                translated_text: trimmedText,
                user_edited: !!trimmedText,
              };
            }
            return { ...prev, [pName]: nextArr };
          });
          addToast(`Fala atualizada no roteiro (.txt) e no mapa (.json)!`, `success`);
          useWorkspaceStore.getState().bumpWorkspaceRevision();
          return;
        }
      } catch (err) {
        console.warn(`[Library] updateBalloonText failed, falling back to saveLibraryFile:`, err);
      }
      await clientApi.saveLibraryFile(activeFile.path, lines.join(`\n`));
      addToast(`Fala atualizada no roteiro (.txt) e no mapa (.json)!`, `success`);
      useWorkspaceStore.getState().bumpWorkspaceRevision();
    } catch (err) {
      console.error(`Erro ao atualizar fala:`, err);
      addToast(`Erro ao salvar fala: ` + (err?.message || err), `error`);
    }
  };

  return { openInStudio, exportScript, deleteLibraryFile, saveBalloonText, syncChapterTxt, isSyncing };
}
