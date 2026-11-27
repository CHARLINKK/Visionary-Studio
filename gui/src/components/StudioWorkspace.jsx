import React from 'react';
import SeamlessEditor from './SeamlessEditor';
import ConfirmModal from './ConfirmModal';
import StudioBatchSidebar from './StudioBatchSidebar';
import { ErrorBoundary } from './ErrorBoundary';
import { useStudioPages } from '../hooks/useStudioPages';
import { useStudioBatchRunner } from '../hooks/useStudioBatchRunner';
import { BookOpen } from 'lucide-react';

import './StudioWorkspace.css';

/**
 * StudioWorkspace Component
 * 
 * Controlador principal da área de trabalho do Studio.
 * Delega o ciclo de vida e navegação de páginas ao hook `useStudioPages`
 * e a orquestração do pipeline de processamento em lote ao hook `useStudioBatchRunner`.
 * 
 * @param {Object} props
 * @param {string} props.folderPath Caminho absoluto do diretório do capítulo ativo.
 * @param {string} props.folderName Nome da pasta/capítulo atual.
 * @param {boolean} props.isActive Indica se a aba Studio está em foco no momento.
 */
export default function StudioWorkspace({ folderPath, folderName, isActive = true }) {
  const {
    pages,
    currentIndex,
    setCurrentIndex,
    activePage,
    loading,
    hasFetchedOnce,
    refreshTrigger,
    setRefreshTrigger,
    selectedPages,
    fetchDirectory,
    handleTogglePage,
    handleSelectAll,
  } = useStudioPages({ folderPath, isActive });

  const {
    setSteps,
    deepValidation,
    setDeepValidation,
    overwrite,
    setOverwrite,
    isSubmitting,
    clearConfirmState,
    setClearConfirmState,
    isClearing,
    canRunOcr,
    canRunTranslate,
    handleProcess,
    requestClear,
    executeClear,
  } = useStudioBatchRunner({
    folderPath,
    folderName,
    pages,
    selectedPages,
    activePage,
    fetchDirectory,
    setRefreshTrigger,
  });

  return (
    <div className="studio-workspace fade-in">
      <div className="studio-main" style={{ position: 'relative' }}>
        {loading && <div className="studio-top-loader" />}
        {folderPath && activePage ? (
          <ErrorBoundary>
            <SeamlessEditor 
              page={activePage} 
              pageIndex={currentIndex}
              totalPages={pages.length}
              refreshTrigger={refreshTrigger}
              onNavigate={(dir) => {
                 let nextIdx = currentIndex + dir;
                 if (nextIdx < 0) nextIdx = 0;
                 if (nextIdx >= pages.length) nextIdx = pages.length - 1;
                 setCurrentIndex(nextIdx);
              }}
            />
          </ErrorBoundary>
        ) : !folderPath ? (
          <div className="empty-state onboarding-card fade-in">
            <div className="onboarding-content">
              <div className="onboarding-icon-orb">
                <BookOpen size={44} style={{ color: 'var(--brand-primary, #8b5cf6)' }} />
              </div>
              <h2 style={{ fontSize: '20px', fontWeight: '700', color: '#f1f5f9', margin: '14px 0 6px 0' }}>
                Bem-vindo ao Visionary Studio
              </h2>
              <p style={{ fontSize: '13px', color: '#94a3b8', maxWidth: '460px', margin: '0 auto 24px auto', lineHeight: '1.6' }}>
                Selecione um capítulo de mangá no explorador lateral para iniciar a leitura, detecção de balões e tradução adaptativa com IA.
              </p>
              <div className="onboarding-steps-grid">
                <div className="onboarding-step-card">
                  <span className="step-num">1</span>
                  <span className="step-text">Escolha a pasta RAW na barra lateral</span>
                </div>
                <div className="onboarding-step-card">
                  <span className="step-num">2</span>
                  <span className="step-text">Configure os modelos na aba Módulos</span>
                </div>
                <div className="onboarding-step-card">
                  <span className="step-num">3</span>
                  <span className="step-text">Acompanhe pelo Console de Telemetria</span>
                </div>
              </div>
            </div>
          </div>
        ) : hasFetchedOnce && !loading && pages.length === 0 ? (
          <div className="empty-state onboarding-card fade-in">
            <div className="onboarding-content">
              <p style={{ color: 'var(--text-secondary)' }}>Nenhuma imagem encontrada neste capítulo.</p>
            </div>
          </div>
        ) : (
          <div className="studio-canvas-placeholder" style={{ flex: 1, height: '100%', background: 'var(--bg-dark)' }} />
        )}
      </div>
      
      {/* Painel de Processamento Lote */}
      <StudioBatchSidebar
        pages={pages}
        selectedPages={selectedPages}
        currentIndex={currentIndex}
        setCurrentIndex={setCurrentIndex}
        handleSelectAll={handleSelectAll}
        handleTogglePage={handleTogglePage}
        requestClear={requestClear}
        isClearing={isClearing}
        canRunOcr={canRunOcr}
        canRunTranslate={canRunTranslate}
        isSubmitting={isSubmitting}
        setSteps={setSteps}
        handleProcess={handleProcess}
        deepValidation={deepValidation}
        setDeepValidation={setDeepValidation}
        overwrite={overwrite}
        setOverwrite={setOverwrite}
      />

      {/* Dialog Box Moderno para Apagar Dados */}
      <ConfirmModal
        isOpen={!!clearConfirmState}
        title={clearConfirmState?.title}
        message={clearConfirmState?.message}
        confirmText={clearConfirmState?.confirmText}
        onConfirm={executeClear}
        onClose={() => setClearConfirmState(null)}
      />
    </div>
  );
}
