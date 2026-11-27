import React from 'react';
import Queue from './Queue';
import {
  Play,
  CheckSquare,
  Square,
  Trash2,
  Layers,
  LayoutDashboard,
  ScanText,
  Languages,
} from 'lucide-react';

/**
 * StudioBatchSidebar Component
 * 
 * Barra lateral seamless e monocromática de ações em lote para páginas do capítulo:
 * - Seleção fluida e status visual por micro-trilho contido (Layout, OCR, Tradução).
 * - Ações de limpeza discretas no cabeçalho do dock.
 * - Disparo individual de cada etapa (Layout, OCR, Tradução) e validação profunda SFX integrada.
 * - Disparo unificado da pipeline e fila de tarefas em background (Queue).
 */
export default function StudioBatchSidebar({
  pages,
  selectedPages,
  currentIndex,
  setCurrentIndex,
  handleSelectAll,
  handleTogglePage,
  requestClear,
  isClearing,
  canRunOcr,
  canRunTranslate,
  isSubmitting,
  setSteps,
  handleProcess,
  deepValidation,
  setDeepValidation,
  overwrite,
  setOverwrite,
}) {
  const allSelected = pages.length > 0 && selectedPages.size === pages.length;
  const selectedCount = selectedPages.size;

  const selectedPagesList = React.useMemo(() => {
    return Array.from(selectedPages).map(i => pages[i]).filter(Boolean);
  }, [selectedPages, pages]);

  const layoutStats = React.useMemo(() => {
    if (selectedCount === 0) return { ready: false, label: '0 selecionadas' };
    const withLayout = selectedPagesList.filter(p => p.pageData?.layout || p.pageData?.blockCount !== undefined).length;
    if (withLayout === selectedCount) return { ready: true, label: 'Pronto' };
    return { ready: true, label: `${withLayout}/${selectedCount} prontos` };
  }, [selectedCount, selectedPagesList]);

  const ocrStats = React.useMemo(() => {
    if (selectedCount === 0) return { ready: false, label: '0 selecionadas' };
    if (!canRunOcr) {
      const missing = selectedPagesList.filter(p => !(p.pageData?.layout || p.pageData?.blockCount !== undefined)).length;
      return { ready: false, isWarning: true, label: missing > 0 ? `Requer Layout (${missing})` : 'Requer Layout' };
    }
    const withOcr = selectedPagesList.filter(p => p.pageData?.ocr || p.pageData?.blockCount === 0).length;
    if (withOcr === selectedCount) return { ready: true, label: 'Pronto' };
    return { ready: true, label: `${withOcr}/${selectedCount} prontos` };
  }, [selectedCount, selectedPagesList, canRunOcr]);

  const translateStats = React.useMemo(() => {
    if (selectedCount === 0) return { ready: false, label: '0 selecionadas' };
    if (!canRunTranslate) {
      const missing = selectedPagesList.filter(p => !(p.pageData?.ocr || p.pageData?.blockCount === 0)).length;
      return { ready: false, isWarning: true, label: missing > 0 ? `Requer OCR (${missing})` : 'Requer OCR' };
    }
    const withTrans = selectedPagesList.filter(p => p.pageData?.translation).length;
    if (withTrans === selectedCount) return { ready: true, label: 'Pronto' };
    return { ready: true, label: `${withTrans}/${selectedCount} prontos` };
  }, [selectedCount, selectedPagesList, canRunTranslate]);

  const getLayoutTooltip = () => {
    if (isSubmitting) return "Processando em segundo plano...";
    if (selectedPages.size === 0) return "Layout desativado: Selecione ao menos uma página na lista acima.";
    return "Executar apenas Layout nas páginas selecionadas";
  };

  const getOcrTooltip = () => {
    if (isSubmitting) return "Processando em segundo plano...";
    if (selectedPages.size === 0) return "OCR desativado: Selecione ao menos uma página na lista acima.";
    if (!canRunOcr) return "OCR desativado: As páginas selecionadas ainda não possuem balões detectados. Execute a Etapa 1 (Layout) primeiro.";
    return "Executar apenas OCR nas páginas selecionadas";
  };

  const getTranslateTooltip = () => {
    if (isSubmitting) return "Processando em segundo plano...";
    if (selectedPages.size === 0) return "Tradução desativada: Selecione ao menos uma página na lista acima.";
    if (!canRunTranslate) return "Tradução desativada: As páginas selecionadas ainda não possuem texto extraído por OCR. Execute a Etapa 2 (OCR) primeiro.";
    return "Executar apenas Tradução nas páginas selecionadas";
  };

  const getMasterTooltip = () => {
    if (isSubmitting) return "Processando fila de tarefas em segundo plano...";
    if (selectedPages.size === 0) return "Selecione páginas na lista acima para processar";
    return `Executa todas as 3 etapas (Layout, OCR e Tradução) nas páginas selecionadas`;
  };

  return (
    <div className="studio-sidebar batch-sidebar">
      {/* 1. Header Seamless */}
      <div className="sidebar-header">
        <h3>
          <Layers size={15} />
          <span>Processamento em Lote</span>
        </h3>
        <button
          type="button"
          className="btn-select-all"
          onClick={handleSelectAll}
          title={allSelected ? "Desmarcar todas as páginas" : "Selecionar todas as páginas"}
        >
          {allSelected ? 'Desmarcar' : 'Todas'}
        </button>
      </div>

      {/* 2. Sub-barra de contagem de páginas */}
      <div className="batch-sub-bar">
        <span className="batch-sub-title">Páginas ({selectedPages.size}/{pages.length})</span>
        <span className="batch-counter-badge">{selectedPages.size} / {pages.length}</span>
      </div>

      {/* 3. Lista Fluida de Páginas (Sem caixas duras ao redor) */}
      <div className="batch-pages-section">
        {pages.map((p, i) => {
          const isSelected = selectedPages.has(i);
          const hasLayout = !!(p.pageData?.layout || p.pageData?.blockCount !== undefined);
          const hasOcr = !!p.pageData?.ocr;
          const hasTranslation = !!p.pageData?.translation;

          return (
            <div
              key={p.path || i}
              id={`batch-page-${i}`}
              className={`batch-page-item ${isSelected ? 'selected' : ''} ${currentIndex === i ? 'active' : ''}`}
              onClick={() => setCurrentIndex(i)}
            >
              <div
                className="checkbox-wrapper"
                onClick={(e) => {
                  e.stopPropagation();
                  handleTogglePage(i);
                }}
              >
                {isSelected ? (
                  <CheckSquare size={15} className="text-brand" />
                ) : (
                  <Square size={15} className="text-muted" />
                )}
              </div>

              <span className="page-name">{p.name}</span>

              {/* Micro-trilho discreto (3 pontos foscos) */}
              <div
                className="vs-micro-track"
                title={`Layout: ${hasLayout ? 'Concluído' : 'Ausente'} • OCR: ${hasOcr ? 'Concluído' : 'Ausente'} • Tradução: ${hasTranslation ? 'Concluído' : 'Ausente'}`}
              >
                <span className={`vs-track-dot ${hasLayout ? 'on-lay' : ''}`} />
                <span className={`vs-track-dot ${hasOcr ? 'on-ocr' : ''}`} />
                <span className={`vs-track-dot ${hasTranslation ? 'on-trn' : ''}`} />
              </div>
            </div>
          );
        })}
      </div>

      {/* 4. Dock Seamless da Pipeline */}
      <div className="batch-pipeline-dock">
        <div className="pipeline-dock-header">
          <span className="dock-title">Pipeline</span>
          <div className="clear-actions-strip">
            <div className="btn-disabled-tooltip-wrapper" title={selectedCount === 0 ? "Selecione ao menos 1 página para apagar traduções" : undefined}>
              <button
                type="button"
                className="btn-clear-ghost"
                title="Apagar apenas traduções"
                disabled={selectedCount === 0 || isClearing}
                onClick={() => requestClear(['translate'])}
              >
                <Trash2 size={11} /> Tradução
              </button>
            </div>
            <div className="btn-disabled-tooltip-wrapper" title={selectedCount === 0 ? "Selecione ao menos 1 página para apagar OCR e Traduções" : undefined}>
              <button
                type="button"
                className="btn-clear-ghost"
                title="Apagar OCR e Traduções"
                disabled={selectedCount === 0 || isClearing}
                onClick={() => requestClear(['ocr', 'translate'])}
              >
                <Trash2 size={11} /> OCR
              </button>
            </div>
            <div className="btn-disabled-tooltip-wrapper" title={selectedCount === 0 ? "Selecione ao menos 1 página para apagar balões, OCR e traduções" : undefined}>
              <button
                type="button"
                className="btn-clear-ghost"
                title="Apagar balões, OCR e traduções"
                disabled={selectedCount === 0 || isClearing}
                onClick={() => requestClear(['layout', 'ocr', 'translate'])}
              >
                <Trash2 size={11} /> Tudo
              </button>
            </div>
          </div>
        </div>

        {/* Estágios Verticais Monocromáticos */}
        <div className="batch-stages-vertical">
          {/* 1. Layout */}
          <div className="batch-stage-row">
            <div className="batch-stage-left">
              <span className="batch-stage-icon">
                <LayoutDashboard size={15} />
              </span>
              <span className="batch-stage-name">1. Layout</span>
              {selectedCount > 0 && layoutStats.label !== 'Pronto' ? (
                <span className="stage-info-pill ready">{layoutStats.label}</span>
              ) : null}
            </div>
            <div className="batch-stage-right">
              <div
                className={`val-sfx-pill ${deepValidation ? 'active' : ''}`}
                onClick={() => setDeepValidation(!deepValidation)}
                title="Utiliza o Florence-2 para analisar o interior de cada balão. Recomendado apenas se houver ruídos/SFX falsos positivos, pois aumenta o tempo de detecção."
              >
                <span className="val-sfx-dot" />
                <span>Filtro SFX</span>
              </div>
              <div className="btn-disabled-tooltip-wrapper" title={selectedCount === 0 || isSubmitting ? getLayoutTooltip() : undefined}>
                <button
                  type="button"
                  className="btn-step-run"
                  title={selectedCount === 0 || isSubmitting ? undefined : getLayoutTooltip()}
                  disabled={selectedCount === 0 || isSubmitting}
                  onClick={() => {
                    const s = { layout: true, ocr: false, translate: false };
                    setSteps(s);
                    handleProcess(s);
                  }}
                >
                  <Play size={9} fill="currentColor" />
                </button>
              </div>
            </div>
          </div>

          {/* 2. OCR */}
          <div className={`batch-stage-row ${canRunOcr && selectedCount > 0 ? '' : 'disabled'}`}>
            <div className="batch-stage-left">
              <span className="batch-stage-icon">
                <ScanText size={15} />
              </span>
              <span className="batch-stage-name">2. OCR</span>
              {selectedCount > 0 && (
                !canRunOcr ? (
                  <span className="stage-info-pill warning" title="Requer que a Etapa 1 (Layout) tenha sido executada nas páginas">{ocrStats.label}</span>
                ) : (
                  <span className="stage-info-pill ready">{ocrStats.label}</span>
                )
              )}
            </div>
            <div className="batch-stage-right">
              <div className="btn-disabled-tooltip-wrapper" title={selectedCount === 0 || isSubmitting || !canRunOcr ? getOcrTooltip() : undefined}>
                <button
                  type="button"
                  className="btn-step-run"
                  title={selectedCount === 0 || isSubmitting || !canRunOcr ? undefined : getOcrTooltip()}
                  disabled={selectedCount === 0 || isSubmitting || !canRunOcr}
                  onClick={() => {
                    const s = { layout: false, ocr: true, translate: false };
                    setSteps(s);
                    handleProcess(s);
                  }}
                >
                  <Play size={9} fill="currentColor" />
                </button>
              </div>
            </div>
          </div>

          {/* 3. Tradução */}
          <div className={`batch-stage-row ${canRunTranslate && selectedCount > 0 ? '' : 'disabled'}`}>
            <div className="batch-stage-left">
              <span className="batch-stage-icon">
                <Languages size={15} />
              </span>
              <span className="batch-stage-name">3. Tradução</span>
              {selectedCount > 0 && (
                !canRunTranslate ? (
                  <span className="stage-info-pill warning" title="Requer que a Etapa 2 (OCR) tenha sido executada nas páginas">{translateStats.label}</span>
                ) : (
                  <span className="stage-info-pill ready">{translateStats.label}</span>
                )
              )}
            </div>
            <div className="batch-stage-right">
              <div className="btn-disabled-tooltip-wrapper" title={selectedCount === 0 || isSubmitting || !canRunTranslate ? getTranslateTooltip() : undefined}>
                <button
                  type="button"
                  className="btn-step-run"
                  title={selectedCount === 0 || isSubmitting || !canRunTranslate ? undefined : getTranslateTooltip()}
                  disabled={selectedCount === 0 || isSubmitting || !canRunTranslate}
                  onClick={() => {
                    const s = { layout: false, ocr: false, translate: true };
                    setSteps(s);
                    handleProcess(s);
                  }}
                >
                  <Play size={9} fill="currentColor" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Opção Sobrescrever Dados */}
        <label className="batch-option-row">
          <span>Sobrescrever dados existentes</span>
          <input
            type="checkbox"
            checked={overwrite}
            onChange={(e) => setOverwrite(e.target.checked)}
          />
        </label>

        {/* Botão Mestre Oficial Visionary */}
        <div className="btn-disabled-tooltip-wrapper master-batch-wrapper" title={selectedCount === 0 || isSubmitting ? getMasterTooltip() : undefined}>
          <button
            type="button"
            className="btn-primary-batch"
            disabled={selectedCount === 0 || isSubmitting}
            title={selectedCount === 0 || isSubmitting ? undefined : getMasterTooltip()}
            onClick={() => {
              const s = { layout: true, ocr: true, translate: true };
              setSteps(s);
              handleProcess(s);
            }}
          >
            <Play size={12} fill="currentColor" />
            <span>
              {selectedCount === 0
                ? 'Selecione Páginas'
                : `Executar Pipeline Completa (${selectedCount} ${selectedCount === 1 ? 'Página' : 'Páginas'})`}
            </span>
          </button>
        </div>
        {selectedCount === 0 && (
          <div className="batch-dock-hint">
            Marque páginas na lista acima ou clique em <strong>Todas</strong> para processar.
          </div>
        )}

        {/* Fila de Processamento em Background */}
        <Queue />
      </div>
    </div>
  );
}
