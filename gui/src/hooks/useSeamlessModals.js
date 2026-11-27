import { useState } from 'react';

/**
 * Hook modular para estados de diálogo e modais do Seamless.
 */
export function useSeamlessModals() {
  const [previewSrc, setPreviewSrc] = useState(null);
  const [isRestartModalOpen, setIsRestartModalOpen] = useState(false);

  return {
    previewSrc,
    setPreviewSrc,
    isRestartModalOpen,
    setIsRestartModalOpen,
  };
}
