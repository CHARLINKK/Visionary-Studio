import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useToast } from '../contexts/ToastContext';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { ImageOff, Trash2 } from 'lucide-react';
import { clientApi, getServerUrl } from '../api/bridge';
import { safeSetStorageItem } from '../utils/storage';
import LightboxCard from './Lightbox/LightboxCard';
import LightboxEmptyState from './Lightbox/LightboxEmptyState';
import LightboxToolbar from './Lightbox/LightboxToolbar';
import LightboxContextMenu from './Lightbox/LightboxContextMenu';
import LightboxQuickLook from './Lightbox/LightboxQuickLook';
import ConfirmModal from './ConfirmModal';
import { useLightboxDragDrop } from '../hooks/useLightboxDragDrop';
import './Lightbox.css';

/**
 * Lightbox Component
 * 
 * Visualizador em grade e organizador de arquivos brutos (imagens) do capítulo ativo.
 * Permite reordenação via drag-and-drop, merge/split de páginas duplas e deleção em lote.
 * Comunica-se com LibraryService no backend para operações de sistema de arquivos.
 */
export default function Lightbox({ activeChapterPath, isActive = true }) {
  const { addToast } = useToast();
  const bumpExplorerRevision = useWorkspaceStore(s => s.bumpExplorerRevision);
  const navigateToStudioPage = useWorkspaceStore(s => s.navigateToStudioPage);

  const [images, setImages] = useState(() => {
    if (!activeChapterPath) return [];
    try {
      const cached = localStorage.getItem(`visionary:cached_pages:${activeChapterPath}`);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const server = getServerUrl() || 'http://127.0.0.1:5000';
          return parsed.map((i) => {
            const encoded = encodeURIComponent(i.path);
            return {
              ...i,
              src: `${server}/api/image?path=${encoded}`,
              thumbSrc: `${server}/api/image?path=${encoded}&thumb=360`,
            };
          });
        }
      }
    } catch (_) {}
    return [];
  });

  const [selectedPaths, setSelectedPaths] = useState([]);
  const [lastSelectedIndex, setLastSelectedIndex] = useState(null);
  const [readingDirection, setReadingDirection] = useState('rtl');
  const [isProcessing, setIsProcessing] = useState(false);
  const [hasUnsavedOrder, setHasUnsavedOrder] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [contextMenu, setContextMenu] = useState(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [quickLookIndex, setQuickLookIndex] = useState(null);

  const helpPopoverRef = useRef(null);
  const gridAreaRef = useRef(null);

  const [gridColumns, setGridColumns] = useState(() => {
    try {
      const saved = localStorage.getItem('visionary:lightbox_columns');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= 1 && parsed <= 8) return parsed;
      }
    } catch (_) {}
    return 4;
  });

  const handleZoomChange = useCallback((delta) => {
    setGridColumns((prev) => {
      const next = Math.max(1, Math.min(8, prev + delta));
      try { localStorage.setItem('visionary:lightbox_columns', String(next)); } catch (_) {}
      return next;
    });
  }, []);

  const {
    draggedIndex,
    dragOverIndex,
    handleDragStart,
    handleDragEnter,
    handleDragOver,
    handleDrop,
    handleDragEnd,
  } = useLightboxDragDrop({ setImages, setHasUnsavedOrder });

  // Fecha popover ao clicar fora
  useEffect(() => {
    if (!showHelp) return;
    const handleClickOutside = (e) => {
      if (helpPopoverRef.current && !helpPopoverRef.current.contains(e.target) && !e.target.closest('.btn-help')) {
        setShowHelp(false);
      }
    };
    window.addEventListener('mousedown', handleClickOutside);
    return () => window.removeEventListener('mousedown', handleClickOutside);
  }, [showHelp]);

  // Carrega imagens da pasta atual
  const loadImages = useCallback(async (silent = false) => {
    if (!activeChapterPath) {
      setImages([]);
      return;
    }
    if (!silent) setIsProcessing(true);
    try {
      const res = await clientApi.listDirectory(activeChapterPath);
      if (res && res.items) {
        const server = getServerUrl() || 'http://127.0.0.1:5000';
        const imgFiles = res.items.filter(i => i.isImage).map(i => {
          const encoded = encodeURIComponent(i.path);
          return {
            ...i,
            src: `${server}/api/image?path=${encoded}`,
            thumbSrc: `${server}/api/image?path=${encoded}&thumb=360`,
          };
        });
        setImages(prev => {
          if (
            prev.length === imgFiles.length && 
            prev.every((p, idx) => p.path === imgFiles[idx].path && p.name === imgFiles[idx].name && p.src === imgFiles[idx].src)
          ) {
            return prev;
          }
          return imgFiles;
        });
        setSelectedPaths(prev => prev.filter(p => imgFiles.some(img => img.path === p)));
        setHasUnsavedOrder(false);
        safeSetStorageItem(
          `visionary:cached_pages:${activeChapterPath}`,
          JSON.stringify(imgFiles),
          'visionary:cached_pages:'
        );
      }
    } catch {
      addToast('Erro ao carregar pasta.', 'error');
    } finally {
      if (!silent) setIsProcessing(false);
    }
  }, [activeChapterPath, addToast]);

  useEffect(() => {
    if (!activeChapterPath) {
      setImages([]);
      return;
    }
    if (!isActive) return;

    try {
      const cached = localStorage.getItem(`visionary:cached_pages:${activeChapterPath}`);
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const server = getServerUrl() || 'http://127.0.0.1:5000';
          const mapped = parsed.map(i => {
            const encoded = encodeURIComponent(i.path);
            return {
              ...i,
              src: `${server}/api/image?path=${encoded}`,
              thumbSrc: `${server}/api/image?path=${encoded}&thumb=360`,
            };
          });
          setImages(prev => (prev.length > 0 && prev[0]?.path?.startsWith(activeChapterPath) ? prev : mapped));
        }
      }
    } catch (_) {}
    loadImages(true);
  }, [activeChapterPath, isActive, loadImages]);

  // Pré-aquecimento das miniaturas das primeiras páginas no cache do navegador
  useEffect(() => {
    if (!isActive) return;
    if (images && images.length > 0) {
      const initialBatch = images.slice(0, 16);
      initialBatch.forEach(img => {
        const targetSrc = img?.thumbSrc || img?.src;
        if (targetSrc) {
          const imgLoader = new Image();
          imgLoader.src = targetSrc;
        }
      });
    }
  }, [images, isActive]);

  const chapterFolderName = useMemo(() => {
    if (!activeChapterPath) return '';
    const parts = activeChapterPath.split(/[/\\]/);
    return parts.filter(Boolean).pop() || activeChapterPath;
  }, [activeChapterPath]);

  const selectedSet = useMemo(() => new Set(selectedPaths), [selectedPaths]);

  // Seleção com suporte a Shift + Clique (seleção contínua em intervalo)
  const toggleSelection = useCallback((path, index = null, e = null) => {
    setSelectedPaths(prev => {
      if (
        e?.shiftKey &&
        lastSelectedIndex !== null &&
        lastSelectedIndex !== undefined &&
        index !== null &&
        index !== undefined &&
        images.length > 0
      ) {
        const start = Math.min(lastSelectedIndex, index);
        const end = Math.max(lastSelectedIndex, index);
        const rangePaths = images.slice(start, end + 1).map(img => img.path);
        const newSet = new Set([...prev, ...rangePaths]);
        return Array.from(newSet);
      }
      return prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path];
    });

    if (index !== null && index !== undefined) {
      setLastSelectedIndex(index);
    }
  }, [images, lastSelectedIndex]);

  const handleDoubleClick = useCallback((img) => {
    if (activeChapterPath && img?.name) {
      navigateToStudioPage({
        folderPath: activeChapterPath,
        pageName: img.name
      });
      addToast(`Abrindo ${img.name} no Estúdio...`, 'info');
    }
  }, [activeChapterPath, navigateToStudioPage, addToast]);

  const selectAll = useCallback(() => setSelectedPaths(images.map(i => i.path)), [images]);
  const clearSelection = useCallback(() => setSelectedPaths([]), []);
  const invertSelection = useCallback(() => {
    setSelectedPaths(prev => {
      const currentSet = new Set(prev);
      return images.filter(i => !currentSet.has(i.path)).map(i => i.path);
    });
  }, [images]);

  const applyOrder = async () => {
    if (!hasUnsavedOrder) return;
    setIsProcessing(true);
    try {
      const res = await clientApi.reorder_pages(activeChapterPath, images);
      if (res.success) {
        addToast('Arquivos renomeados com sucesso!', 'success');
        await loadImages();
        bumpExplorerRevision();
      } else {
        addToast('Erro ao reordenar: ' + res.error, 'error');
      }
    } catch {
      addToast('Erro de comunicação.', 'error');
    }
    setIsProcessing(false);
  };

  const discardOrder = useCallback(async () => {
    setIsProcessing(true);
    await loadImages(true);
    setHasUnsavedOrder(false);
    setIsProcessing(false);
    addToast('Alterações de ordem descartadas.', 'info');
  }, [loadImages, addToast]);

  const handleMerge = async () => {
    if (selectedPaths.length < 2) return;
    if (hasUnsavedOrder) {
      addToast('Aplique a ordem primeiro antes de unir páginas.', 'warning');
      return;
    }
    setIsProcessing(true);
    try {
      const orderedPaths = images
        .filter(img => selectedPaths.includes(img.path))
        .map(img => img.path);

      const res = await clientApi.merge_pages(activeChapterPath, orderedPaths, readingDirection);
      if (res.success) {
        addToast('Páginas unidas com sucesso!', 'success');
        await loadImages();
        bumpExplorerRevision();
      } else {
        addToast('Erro ao unir: ' + res.error, 'error');
      }
    } catch {
      addToast('Erro ao unir páginas.', 'error');
    }
    setIsProcessing(false);
  };

  const handleSplit = async () => {
    if (selectedPaths.length !== 1) return;
    if (hasUnsavedOrder) {
      addToast('Aplique a ordem primeiro antes de dividir páginas.', 'warning');
      return;
    }
    setIsProcessing(true);
    try {
      const res = await clientApi.split_page(selectedPaths[0], readingDirection);
      if (res.success) {
        addToast('Página dividida com sucesso!', 'success');
        await loadImages();
        bumpExplorerRevision();
      } else {
        addToast('Erro ao dividir: ' + res.error, 'error');
      }
    } catch {
      addToast('Erro ao dividir página.', 'error');
    }
    setIsProcessing(false);
  };

  const handleDelete = useCallback(() => {
    if (selectedPaths.length === 0) return;
    if (hasUnsavedOrder) {
      addToast('Aplique a ordem primeiro antes de excluir páginas.', 'warning');
      return;
    }
    setDeleteModalOpen(true);
  }, [selectedPaths.length, hasUnsavedOrder, addToast]);

  const confirmDelete = async () => {
    setDeleteModalOpen(false);
    setIsProcessing(true);
    try {
      let successCount = 0;
      for (const p of selectedPaths) {
        const res = await clientApi.delete_page(p);
        if (res.success) successCount++;
      }
      addToast(`${successCount} página(s) apagada(s).`, 'success');
      setSelectedPaths([]);
      await loadImages();
      bumpExplorerRevision();
    } catch {
      addToast('Erro ao apagar páginas.', 'error');
    }
    setIsProcessing(false);
  };

  const handleCardContextMenu = useCallback((e, img, index) => {
    setSelectedPaths(prev => {
      if (!prev.includes(img.path)) {
        return [img.path];
      }
      return prev;
    });
    setLastSelectedIndex(index);
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      img,
      index,
    });
  }, []);

  // Atalhos de teclado no modo Lightbox
  useEffect(() => {
    if (!isActive) return;

    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        return;
      }

      // Escape: fecha modal / menu de contexto / ajuda / limpa seleção
      if (e.key === 'Escape') {
        if (quickLookIndex !== null) {
          setQuickLookIndex(null);
          return;
        }
        if (deleteModalOpen) {
          setDeleteModalOpen(false);
          return;
        }
        if (contextMenu) {
          setContextMenu(null);
          return;
        }
        if (showHelp) {
          setShowHelp(false);
          return;
        }
        if (selectedPaths.length > 0) {
          clearSelection();
          return;
        }
      }

      // Se o modal de exclusão ou Quick Look estiver aberto, não aciona atalhos de fundo da grade
      if (deleteModalOpen || quickLookIndex !== null) {
        return;
      }

      // Espaço: Pré-visualização rápida (Quick Look)
      if (e.code === 'Space') {
        e.preventDefault();
        if (selectedPaths.length > 0) {
          const idx = images.findIndex(img => img.path === selectedPaths[0]);
          setQuickLookIndex(idx >= 0 ? idx : 0);
        } else if (images.length > 0) {
          setQuickLookIndex(0);
        }
        return;
      }

      // Ctrl + A: Selecionar todas
      if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A')) {
        e.preventDefault();
        selectAll();
        return;
      }

      // Delete: excluir selecionadas
      if (e.key === 'Delete' && selectedPaths.length > 0 && !isProcessing) {
        e.preventDefault();
        handleDelete();
        return;
      }

      // Enter: se 1 página selecionada e modal não estiver aberto, abre no Estúdio
      if (e.key === 'Enter' && selectedPaths.length === 1 && !deleteModalOpen && quickLookIndex === null) {
        const targetImg = images.find(img => img.path === selectedPaths[0]);
        if (targetImg) {
          handleDoubleClick(targetImg);
        }
        return;
      }

      // Zoom + e -
      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        handleZoomChange(-1);
        return;
      }
      if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        handleZoomChange(1);
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    isActive,
    quickLookIndex,
    deleteModalOpen,
    contextMenu,
    showHelp,
    selectedPaths,
    isProcessing,
    selectAll,
    clearSelection,
    handleDelete,
    images,
    handleDoubleClick,
    handleZoomChange,
  ]);

  // Zoom da grade com Ctrl + Scroll
  useEffect(() => {
    const el = gridAreaRef.current;
    if (!el) return;

    const handleWheel = (e) => {
      if (e.ctrlKey) {
        e.preventDefault();
        if (e.deltaY < 0) {
          handleZoomChange(-1);
        } else if (e.deltaY > 0) {
          handleZoomChange(1);
        }
      }
    };

    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [handleZoomChange]);

  if (!activeChapterPath) {
    return <LightboxEmptyState />;
  }

  return (
    <div className="lightbox-container">
      <LightboxToolbar
        activeChapterPath={activeChapterPath}
        chapterFolderName={chapterFolderName}
        imagesCount={images.length}
        selectedCount={selectedPaths.length}
        selectAll={selectAll}
        clearSelection={clearSelection}
        readingDirection={readingDirection}
        setReadingDirection={setReadingDirection}
        handleMerge={handleMerge}
        handleSplit={handleSplit}
        handleDelete={handleDelete}
        hasUnsavedOrder={hasUnsavedOrder}
        applyOrder={applyOrder}
        discardOrder={discardOrder}
        isProcessing={isProcessing}
        handleZoomChange={handleZoomChange}
        gridColumns={gridColumns}
        loadImages={loadImages}
        showHelp={showHelp}
        setShowHelp={setShowHelp}
        helpPopoverRef={helpPopoverRef}
      />

      {/* ÁREA DE GRADE DE CARDS */}
      <div 
        ref={gridAreaRef}
        className="lightbox-grid-area" 
        onDragOver={handleDragOver}
      >
        <div 
          className="lightbox-grid"
          style={{ 
            '--grid-cols': gridColumns,
            gridTemplateColumns: `repeat(${gridColumns}, minmax(0, 1fr))`
          }}
        >
          {images.length === 0 && !isProcessing && (
            <div className="lightbox-no-images">
              <ImageOff size={32} />
              <p>Nenhuma imagem suportada encontrada nesta pasta.</p>
            </div>
          )}

          {images.map((img, index) => (
            <LightboxCard
              key={img.path}
              img={img}
              index={index}
              isSelected={selectedSet.has(img.path)}
              isDragging={draggedIndex === index}
              isDragOver={dragOverIndex === index}
              onToggleSelection={toggleSelection}
              onDoubleClick={handleDoubleClick}
              onContextMenu={handleCardContextMenu}
              onDragStart={handleDragStart}
              onDragEnter={handleDragEnter}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onDragEnd={handleDragEnd}
            />
          ))}
        </div>
      </div>

      {contextMenu && (
        <LightboxContextMenu
          isOpen={Boolean(contextMenu)}
          x={contextMenu.x}
          y={contextMenu.y}
          targetImg={contextMenu.img}
          selectedCount={selectedPaths.length}
          onClose={() => setContextMenu(null)}
          onOpenInStudio={handleDoubleClick}
          onMerge={handleMerge}
          onSplit={handleSplit}
          onDelete={handleDelete}
          onSelectAll={selectAll}
          onInvertSelection={invertSelection}
          addToast={addToast}
        />
      )}

      {/* Modal Temático de Confirmação de Exclusão */}
      <ConfirmModal
        isOpen={deleteModalOpen}
        title={`Excluir ${selectedPaths.length} Página(s)?`}
        message={`Tem certeza que deseja apagar permanentemente ${selectedPaths.length === 1 ? 'esta página' : 'estas páginas'} do disco? Esta ação não pode ser desfeita.`}
        confirmText="Excluir Definitivamente"
        cancelText="Cancelar"
        icon={Trash2}
        onConfirm={confirmDelete}
        onClose={() => setDeleteModalOpen(false)}
      />

      {/* Modal de Pré-visualização Rápida (Quick Look) */}
      <LightboxQuickLook
        isOpen={quickLookIndex !== null}
        images={images}
        currentIndex={quickLookIndex ?? 0}
        onClose={() => setQuickLookIndex(null)}
        onNavigate={(newIdx) => setQuickLookIndex(newIdx)}
        onOpenInStudio={handleDoubleClick}
      />
    </div>
  );
}
