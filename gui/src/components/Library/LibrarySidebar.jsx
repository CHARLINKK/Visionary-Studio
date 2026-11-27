import React, { useState, useMemo } from "react";
import { FolderOpen, RefreshCw, Minus, Search, X, Trash2, BookOpen } from "lucide-react";
import { useLibraryStore } from "../../stores/useLibraryStore";
import { useToast } from "../../contexts/ToastContext";
import { clientApi } from "../../api/bridge";

const formatSize = (bytes) => {
  if (!bytes || isNaN(bytes)) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
};

const formatDate = (ts) => (!ts || isNaN(ts) ? "" : new Date(ts).toLocaleDateString());

const LibraryFileItem = React.memo(function LibraryFileItem({
  file,
  isActive,
  isConfirming,
  onSelect,
  onDelete,
}) {
  const chapterDisplayName = file.name.replace(/\.txt$/i, "");
  const metaText = [
    formatDate(file.mtime),
    file.size ? formatSize(file.size) : null
  ].filter(Boolean).join(" • ");
  const fullTooltip = `${chapterDisplayName}${metaText ? `\n${metaText}` : ""}`;

  return (
    <div
      className={`library-file-item ${isActive ? "active" : ""}`}
      onClick={onSelect}
      title={fullTooltip}
    >
      <BookOpen size={15} className="explorer-icon-chapter" />
      <div className="item-content-wrap">
        <span className="item-name">
          {chapterDisplayName}
        </span>
        {file.status === "complete" ? (
          <span
            className="file-status-pill complete"
            title="100% dos balões traduzidos"
          >
            ✓ Pronto
          </span>
        ) : file.pendingCount > 0 ? (
          <span
            className="file-status-pill pending"
            title={`${file.pendingCount} balões com tradução pendente`}
          >
            ⏳ {file.pendingCount}
          </span>
        ) : file.balloonCount > 0 ? (
          <span className="explorer-page-pill" title={`${file.balloonCount} balões`}>
            {file.balloonCount} balões
          </span>
        ) : null}
        <button
          type="button"
          className={`btn-delete-file ${isConfirming ? "is-confirming" : ""}`}
          onClick={onDelete}
          title={isConfirming ? `Clique novamente para confirmar a exclusão de "${chapterDisplayName}"` : "Excluir arquivo da Biblioteca"}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
});

export default function LibrarySidebar({
  sidebarCollapsed,
  setSidebarCollapsed,
  openLibraryFolder,
  refreshLibrary,
  isLoading,
  loadLibraryFile,
  deleteLibraryFile,
}) {
  const libraryFiles = useLibraryStore((s) => s.libraryFiles);
  const activeFile = useLibraryStore((s) => s.activeFile);
  const { addToast } = useToast();

  const [confirmingPath, setConfirmingPath] = useState(null);
  const confirmTimerRef = React.useRef(null);

  React.useEffect(() => {
    return () => {
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    };
  }, []);

  const handleDelete = (e, file) => {
    if (e && typeof e.stopPropagation === "function") e.stopPropagation();
    if (!file) return;

    if (confirmingPath !== file.path) {
      setConfirmingPath(file.path);
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
      confirmTimerRef.current = setTimeout(() => {
        setConfirmingPath((current) => (current === file.path ? null : current));
      }, 4000);
      if (deleteLibraryFile) deleteLibraryFile(e, file);
      return;
    }

    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    setConfirmingPath(null);
    if (deleteLibraryFile) deleteLibraryFile(e, file);
  };

  const [sidebarSearchText, setSidebarSearchText] = useState("");

  const filteredLibraryFiles = useMemo(() => {
    if (!sidebarSearchText.trim()) return libraryFiles;
    const query = sidebarSearchText.toLowerCase();
    return libraryFiles.filter((f) => f.name.toLowerCase().includes(query));
  }, [libraryFiles, sidebarSearchText]);

  return (
    <div className={`library-sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
      <div className="library-sidebar-header">
        <div className="sidebar-title-row" style={{ userSelect: "none" }}>
          <h3 style={{ margin: 0, fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "1px", textTransform: "uppercase" }}>
            CAPÍTULOS
          </h3>
        </div>
        <div className="sidebar-actions">
          <button
            type="button"
            className="btn-lib-icon btn-toggle-sidebar btn-collapse-lib-sidebar"
            onClick={() => setSidebarCollapsed(true)}
            title="Recolher lista de capítulos"
          >
            <Minus size={15} />
          </button>
        </div>
      </div>

      <div className="explorer-toolbar library-toolbar">
        <div className="explorer-nav-row">
          <button
            type="button"
            className="btn-explorer-up"
            onClick={async () => {
              if (openLibraryFolder) {
                openLibraryFolder();
                return;
              }
              try {
                if (activeFile?.path) {
                  const res = await clientApi.openFileInExplorer(activeFile.path);
                  if (res && res.success !== false) addToast("Pasta do capítulo aberta no Explorer!", "info");
                  else addToast(`Erro: ${res?.error || "Desconhecido"}`, "error");
                } else {
                  const res = await clientApi.openLibraryFolder();
                  if (res && res.success !== false) addToast("Pasta da biblioteca aberta no Explorer!", "info");
                  else addToast(`Erro: ${res?.error || "Desconhecido"}`, "error");
                }
              } catch (e) {
                addToast(`Falha ao conectar com o Explorer: ${e.message}`, "error");
              }
            }}
            title="Abrir pasta dos capítulos no Windows Explorer"
          >
            <FolderOpen size={13} />
            <span>Biblioteca</span>
          </button>
          <button
            type="button"
            className="btn-explorer-refresh"
            onClick={refreshLibrary}
            title="Atualizar lista de capítulos"
          >
            <RefreshCw size={13} className={isLoading ? "spin" : ""} />
          </button>
        </div>

        <div className="explorer-search-box">
          <Search size={13} className="explorer-search-icon" />
          <input
            type="text"
            className="explorer-search-input"
            placeholder="Filtrar capítulos..."
            value={sidebarSearchText}
            onChange={(e) => setSidebarSearchText(e.target.value)}
          />
          {sidebarSearchText && (
            <button
              type="button"
              className="explorer-search-clear"
              onClick={() => setSidebarSearchText("")}
              title="Limpar filtro"
            >
              <X size={12} />
            </button>
          )}
        </div>
      </div>
      <div className="library-file-list">
        {isLoading && libraryFiles.length === 0 ? (
          <div className="empty-message">Carregando capítulos...</div>
        ) : filteredLibraryFiles.length === 0 ? (
          <div className="empty-message">Nenhum capítulo encontrado.</div>
        ) : (
          filteredLibraryFiles.map((file) => (
            <LibraryFileItem
              key={file.path}
              file={file}
              isActive={activeFile?.path === file.path}
              isConfirming={confirmingPath === file.path}
              onSelect={() => loadLibraryFile(file)}
              onDelete={(e) => handleDelete(e, file)}
            />
          ))
        )}
      </div>
    </div>
  );
}
