import React from 'react';
import { createPortal } from 'react-dom';
import {
  X, Activity, Copy, Check, Search,
  AlertTriangle, CheckCircle, XCircle, Clock,
  ArrowDown, Maximize2, Minimize2, Layers, Zap, Trash2
} from 'lucide-react';

// Subcomponente de Alta Performance para Linhas do Terminal
export const LogStreamLine = React.memo(function LogStreamLine({ log }) {
  const isError = log.includes('[ERRO]') || log.toLowerCase().includes('error') || log.toLowerCase().includes('exception') || log.toLowerCase().includes('traceback');
  const isWarning = log.includes('[AVISO]') || log.toLowerCase().includes('warning');
  const isSuccess = log.includes('=== INICIANDO') || log.includes('CONCLUÍDO') || log.includes('Dados salvos') || log.includes('sucesso') || log.includes('[SUCCESS]');

  let timestamp = "";
  let message = log;

  const timestampMatch = log.match(/^\[\d{2}:\d{2}:\d{2}\]/);
  if (timestampMatch) {
    timestamp = timestampMatch[0];
    message = log.substring(timestamp.length).trim();
  }

  // Identificação de Tag de Etapa
  let tag = null;
  const tagMatch = message.match(/^\[([A-Z0-9_Á-Úa-z\s-]+)\]/);
  if (tagMatch) {
    tag = tagMatch[1];
    message = message.substring(tagMatch[0].length).trim();
  }

  let lineClass = 'stream-line';
  if (isError) lineClass += ' line-error';
  else if (isWarning) lineClass += ' line-warning';
  else if (isSuccess) lineClass += ' line-success';

  return (
    <div className={lineClass}>
      {timestamp && <span className="stream-time">{timestamp}</span>}
      {tag && <span className={`stream-tag tag-${tag.toLowerCase().replace(/[^a-z0-9]/g, '')}`}>{tag}</span>}
      <span className="stream-message">{message}</span>
    </div>
  );
});

export default function QueueTerminalModal({
  logModalJob,
  setLogModalJobId,
  isExpanded,
  setIsExpanded,
  copied,
  handleCopyLogs,
  handleClearLogs,
  stats,
  activeFilter,
  setActiveFilter,
  searchQuery,
  setSearchQuery,
  autoScroll,
  setAutoScroll,
  logContainerRef,
  handleLogScroll,
  filteredLogs,
}) {
  if (!logModalJob) return null;

  return createPortal(
    <div className="log-drawer-overlay" onClick={() => setLogModalJobId(null)}>
      <div 
        className={`log-drawer ${isExpanded ? 'expanded' : ''}`} 
        onClick={e => e.stopPropagation()}
      >
        {/* Topbar com Título, Status e Ações */}
        <div className="log-drawer-header">
          <div className="log-drawer-identity">
            <div className={`log-status-indicator ${logModalJob.status}`}>
              {logModalJob.status === 'running' && <span className="pulsing-core" />}
              {logModalJob.status === 'completed' && <CheckCircle size={14} />}
              {(logModalJob.status === 'failed' || logModalJob.status === 'cancelled') && <XCircle size={14} />}
            </div>
            <div>
              <div className="log-drawer-title">
                <span>Console de Execução</span>
                <span className="log-target-chip">
                  {logModalJob.payload?.chapterName || logModalJob.page || 'Lote'}
                </span>
              </div>
              <div className="log-drawer-subtitle">
                {logModalJob.status === 'running' ? (logModalJob.currentStepLabel || 'Em processamento ativo...') :
                 logModalJob.status === 'completed' ? 'Execução concluída com sucesso' :
                 logModalJob.status === 'cancelled' ? 'Execução cancelada pelo usuário' :
                 logModalJob.status === 'failed' ? (logModalJob.error || 'Falha detectada') : 'Aguardando início'}
              </div>
            </div>
          </div>

          <div className="log-drawer-controls">
            <button 
              className="log-tool-btn" 
              onClick={() => setIsExpanded(!isExpanded)}
              title={isExpanded ? "Reduzir largura" : "Expandir console"}
            >
              {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
            <button 
              className={`log-tool-btn ${copied ? 'success' : ''}`} 
              onClick={handleCopyLogs} 
              title="Copiar log completo"
            >
              {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
            </button>
            <button 
              className="log-tool-btn" 
              onClick={handleClearLogs} 
              title="Limpar logs deste console"
            >
              <Trash2 size={14} />
            </button>
            <button 
              className="log-tool-btn close" 
              onClick={() => setLogModalJobId(null)}
              title="Fechar (ESC)"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Barra de Progresso Fina Integrada */}
        <div className="log-progress-strip">
          <div 
            className={`log-progress-fill ${logModalJob.status}`}
            style={{ width: `${logModalJob.progress || (logModalJob.status === 'completed' ? 100 : 0)}%` }}
          />
        </div>

        {/* Painel HUD de Telemetria / Métricas */}
        <div className="log-drawer-telemetry">
          <div className="telemetry-card">
            <div className="telemetry-label">
              <Clock size={11} /> TEMPO TOTAL
            </div>
            <div className="telemetry-value mono">{stats.timeElapsed}</div>
          </div>

          <div className="telemetry-card">
            <div className="telemetry-label">
              <Zap size={11} /> PROGRESSO
            </div>
            <div className="telemetry-value">
              {logModalJob.progress || 0}<span className="unit">%</span>
            </div>
          </div>

          <div 
            className={`telemetry-card clickable ${stats.errorCount > 0 ? 'alert' : ''}`}
            onClick={() => setActiveFilter(activeFilter === 'errors' ? 'all' : 'errors')}
            title="Clique para filtrar apenas erros"
          >
            <div className="telemetry-label">
              <AlertTriangle size={11} /> ERROS
            </div>
            <div className="telemetry-value" style={{ color: stats.errorCount > 0 ? '#ef4444' : 'var(--text-main)' }}>
              {stats.errorCount}
            </div>
          </div>

          <div 
            className="telemetry-card clickable"
            onClick={() => setActiveFilter(activeFilter === 'warnings' ? 'all' : 'warnings')}
            title="Clique para filtrar apenas avisos"
          >
            <div className="telemetry-label">AVISOS</div>
            <div className="telemetry-value" style={{ color: stats.warningCount > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
              {stats.warningCount}
            </div>
          </div>

          {logModalJob.vramState && (
            <div className="telemetry-card vram-card">
              <div className="vram-card-info">
                <div className={`vram-card-label${logModalJob.vramState.done ? ' done' : ''}`}>
                  <Layers size={9} />
                  VRAM — {logModalJob.vramState.model}
                </div>
                <div className="vram-card-numbers">
                  {logModalJob.vramState.done
                    ? 'Carregado ✓'
                    : `${Math.round(logModalJob.vramState.loaded)} / ${Math.round(logModalJob.vramState.total)} MB`
                  }
                </div>
              </div>
              <div className="vram-card-bar-wrap">
                <div className="vram-bar-track">
                  <div
                    className={`vram-bar-fill${logModalJob.vramState.done ? ' done' : ''}`}
                    style={{ width: `${logModalJob.vramState.progress}%` }}
                  />
                </div>
                <div className="vram-bar-pct">{logModalJob.vramState.progress}%</div>
              </div>
            </div>
          )}
        </div>

        {/* Painel VRAM Realtime */}
        {logModalJob.vramRealtime && logModalJob.status === 'running' && (() => {
          const totalGpu = Number(logModalJob.vramRealtime.total_gpu) > 0 ? Number(logModalJob.vramRealtime.total_gpu) : 1;
          const usedMb = Number(logModalJob.vramRealtime.used_mb) || 0;
          const totalPct = Math.min(100, Math.max(0, (usedMb / totalGpu) * 100)).toFixed(1);
          const breakdown = logModalJob.vramRealtime.breakdown || {};
          const hasBreakdown = Object.keys(breakdown).length > 0;

          return (
            <div className="vram-realtime-panel">
              <div className="vram-rt-header">
                <div className="vram-rt-title">
                  <Activity size={11} />
                  VRAM GPU — Tempo Real
                </div>
                <div className="vram-rt-total-text">
                  {usedMb} / {logModalJob.vramRealtime.total_gpu || 0} MB
                </div>
              </div>
              <div className="vram-rt-total-bar-track">
                <div
                  className="vram-rt-total-bar-fill"
                  style={{ width: `${totalPct}%` }}
                />
              </div>
              {hasBreakdown && (
                <div className="vram-rt-breakdown">
                  {Object.entries(breakdown)
                    .sort((a, b) => (Number(b[1]) || 0) - (Number(a[1]) || 0))
                    .map(([name, mb]) => {
                      const numMb = Number(mb) || 0;
                      const pct = Math.min(100, Math.max(0, (numMb / totalGpu) * 100));
                      return (
                        <div key={name} className="vram-rt-row">
                          <div className="vram-rt-row-name" title={name}>{name}</div>
                          <div className="vram-rt-row-bar-wrap">
                            <div className="vram-rt-row-track">
                              <div className="vram-rt-row-fill" style={{ width: `${pct.toFixed(1)}%` }} />
                            </div>
                          </div>
                          <div className="vram-rt-row-mb">{Math.round(numMb)}<span className="vram-unit"> MB</span></div>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>
          );
        })()}

        {/* Stepper Visual de Fases da Pipeline */}
        <div className="log-stepper-track">
          <div className={`step-node ${stats.stagesSeen.has('layout') ? 'done' : ''}`}>
            <span className="node-dot" />
            <span className="node-label">1. Layout</span>
          </div>
          <div className="step-connector" />
          <div className={`step-node ${stats.stagesSeen.has('ocr') ? 'done' : ''}`}>
            <span className="node-dot" />
            <span className="node-label">2. OCR</span>
          </div>
          <div className="step-connector" />
          <div className={`step-node ${stats.stagesSeen.has('translate') ? 'done' : ''}`}>
            <span className="node-dot" />
            <span className="node-label">3. Tradução</span>
          </div>
          <div className="step-connector" />
          <div className={`step-node ${logModalJob.status === 'completed' ? 'done' : ''}`}>
            <span className="node-dot" />
            <span className="node-label">4. Concluído</span>
          </div>
        </div>

        {/* Toolbar de Filtro e Busca */}
        <div className="log-toolbar">
          <div className="log-search-box">
            <Search size={13} className="search-icon" />
            <input 
              type="text" 
              placeholder="Filtrar saída em tempo real (grep)..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="log-search-input"
            />
            {searchQuery && (
              <button className="clear-search" onClick={() => setSearchQuery('')}>
                <X size={12} />
              </button>
            )}
          </div>

          <div className="log-filter-chips">
            <button 
              className={`filter-chip ${activeFilter === 'all' ? 'active' : ''}`}
              onClick={() => setActiveFilter('all')}
            >
              Todos ({logModalJob.logs?.length || 0})
            </button>
            <button 
              className={`filter-chip ${activeFilter === 'errors' ? 'active alert' : ''}`}
              onClick={() => setActiveFilter('errors')}
            >
              Erros ({stats.errorCount})
            </button>
            <button 
              className={`filter-chip ${activeFilter === 'warnings' ? 'active warning' : ''}`}
              onClick={() => setActiveFilter('warnings')}
            >
              Avisos ({stats.warningCount})
            </button>
            <button 
              className={`filter-chip ${activeFilter === 'pipeline' ? 'active' : ''}`}
              onClick={() => setActiveFilter('pipeline')}
            >
              Pipeline
            </button>
          </div>

          <button 
            className={`scroll-lock-btn ${autoScroll ? 'active' : ''}`}
            onClick={() => {
              setAutoScroll(!autoScroll);
              if (!autoScroll && logContainerRef.current) {
                logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
              }
            }}
            title={autoScroll ? "Auto-Scroll Ativo (Travar no fim)" : "Auto-Scroll Desativado (Rolar livre)"}
          >
            <ArrowDown size={12} />
            <span>{autoScroll ? 'Fixado' : 'Livre'}</span>
          </button>
        </div>

        {/* Terminal Stream Body */}
        <div 
          className="log-stream-container" 
          ref={logContainerRef} 
          onScroll={handleLogScroll}
        >
          {filteredLogs.length > 0 ? (
            filteredLogs.map((line, i) => (
              <LogStreamLine key={i} log={line} />
            ))
          ) : (
            <div className="log-empty-state">
              {logModalJob.logs && logModalJob.logs.length > 0 ? (
                <span>Nenhum log encontrado correspondente ao filtro aplicado.</span>
              ) : (
                <>
                  <Activity size={16} className="spin" />
                  <span>Aguardando fluxo de telemetria do motor de processamento...</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
