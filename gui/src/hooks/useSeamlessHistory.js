import { useState, useRef, useCallback, useEffect, useMemo } from 'react';

export function useSeamlessHistory(ocrDataRef, setOcrData) {
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);
  // Espelha os stacks em refs porque callbacks do Konva capturam closures antigas
  // e precisam ler o topo da pilha de forma síncrona durante drag/draw.
  const undoStackRef = useRef([]);
  const redoStackRef = useRef([]);
  const historyTimeoutRef = useRef(null);
  const historyPendingStateRef = useRef(null);

  useEffect(() => {
    return () => {
      if (historyTimeoutRef.current) {
        clearTimeout(historyTimeoutRef.current);
        historyTimeoutRef.current = null;
      }
    };
  }, []);

  const pushHistory = useCallback((state) => {
    if (state) {
      const currentUndo = undoStackRef.current;
      if (currentUndo.length > 0 && currentUndo[currentUndo.length - 1] === state) {
        return;
      }
      // Limita a pilha a 30 snapshots porque arrays de polígonos crescem rápido em RAM.
      const nextUndo = [...currentUndo, state].slice(-30);
      undoStackRef.current = nextUndo;
      setUndoStack(nextUndo);
      redoStackRef.current = [];
      setRedoStack([]);
    }
  }, []);

  const handleUndo = useCallback(() => {
    const currentUndo = undoStackRef.current;
    if (currentUndo.length === 0) return;
    const targetState = currentUndo[currentUndo.length - 1];
    const nextUndo = currentUndo.slice(0, -1);
    undoStackRef.current = nextUndo;
    setUndoStack(nextUndo);

    if (ocrDataRef.current) {
      const nextRedo = [...redoStackRef.current, ocrDataRef.current].slice(-30);
      redoStackRef.current = nextRedo;
      setRedoStack(nextRedo);
    }
    setOcrData(targetState);
  }, [ocrDataRef, setOcrData]);

  const handleRedo = useCallback(() => {
    const currentRedo = redoStackRef.current;
    if (currentRedo.length === 0) return;
    const targetState = currentRedo[currentRedo.length - 1];
    const nextRedo = currentRedo.slice(0, -1);
    redoStackRef.current = nextRedo;
    setRedoStack(nextRedo);

    if (ocrDataRef.current) {
      const nextUndo = [...undoStackRef.current, ocrDataRef.current].slice(-30);
      undoStackRef.current = nextUndo;
      setUndoStack(nextUndo);
    }
    setOcrData(targetState);
  }, [ocrDataRef, setOcrData]);

  // Transação agrupa arrastes contínuos no canvas (drag/resize) em um único Ctrl+Z.
  const startHistoryTransaction = useCallback(() => {
    if (!historyPendingStateRef.current && ocrDataRef.current) {
      historyPendingStateRef.current = ocrDataRef.current;
    }
  }, [ocrDataRef]);

  const commitHistoryTransaction = useCallback(() => {
    if (historyPendingStateRef.current) {
      if (historyPendingStateRef.current !== ocrDataRef.current) {
        pushHistory(historyPendingStateRef.current);
      }
      historyPendingStateRef.current = null;
    }
    if (historyTimeoutRef.current) {
      clearTimeout(historyTimeoutRef.current);
      historyTimeoutRef.current = null;
    }
  }, [ocrDataRef, pushHistory]);

  const clearHistory = useCallback(() => {
    undoStackRef.current = [];
    redoStackRef.current = [];
    setUndoStack([]);
    setRedoStack([]);
    historyPendingStateRef.current = null;
    if (historyTimeoutRef.current) {
      clearTimeout(historyTimeoutRef.current);
      historyTimeoutRef.current = null;
    }
  }, []);

  return useMemo(() => ({
    undoStack,
    redoStack,
    handleUndo,
    handleRedo,
    startHistoryTransaction,
    commitHistoryTransaction,
    pushHistory,
    clearHistory,
    historyTimeoutRef
  }), [
    undoStack,
    redoStack,
    handleUndo,
    handleRedo,
    startHistoryTransaction,
    commitHistoryTransaction,
    pushHistory,
    clearHistory
  ]);
}
