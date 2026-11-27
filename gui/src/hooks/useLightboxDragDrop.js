import { useState, useCallback } from 'react';

/**
 * Hook especializado na gestão de drag-and-drop e reordenação de páginas da Lightbox.
 */
export function useLightboxDragDrop({ setImages, setHasUnsavedOrder }) {
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  const handleDragStart = useCallback((e, index) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragEnter = useCallback((e, index) => {
    e.preventDefault();
    setDragOverIndex(prev => (prev === index ? prev : index));
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  const handleDrop = useCallback((e, dropIndex) => {
    e.preventDefault();
    setDraggedIndex(currentDraggedIndex => {
      if (currentDraggedIndex === null || currentDraggedIndex === dropIndex) {
        setDragOverIndex(null);
        return null;
      }
      setImages(prev => {
        const newImages = [...prev];
        const draggedItem = newImages[currentDraggedIndex];
        newImages.splice(currentDraggedIndex, 1);
        newImages.splice(dropIndex, 0, draggedItem);
        return newImages;
      });
      setHasUnsavedOrder(true);
      setDragOverIndex(null);
      return null;
    });
  }, [setHasUnsavedOrder, setImages]);

  const handleDragEnd = useCallback(() => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  }, []);

  return {
    draggedIndex,
    dragOverIndex,
    handleDragStart,
    handleDragEnter,
    handleDragOver,
    handleDrop,
    handleDragEnd,
  };
}
