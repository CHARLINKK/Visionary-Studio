import React from 'react';
import { X, Terminal } from 'lucide-react';
import { useBatchQueue } from '../hooks/useBatchQueue';
import QueueTerminalModal from './Queue/QueueTerminalModal';
import './Queue.css';

/**
 * Queue Component
 * 
 * Componente global responsável por rastrear as filas de processamento em segundo plano.
 * Ouve eventos do `useWorkspaceStore` e intercepta logs WebSocket do Python.
 * Renderiza cards compactos na sidebar e delega o console de telemetria técnica
 * ao `QueueTerminalModal`.
 */
export default function Queue() {
  const {
    jobQueue,
    completedJobs,
    handleCancelJob,
    clearCompletedJobs,
    setLogModalJobId,
    logModalJob,
    autoScroll,
    setAutoScroll,
    handleLogScroll,
    logContainerRef,
    copied,
    handleCopyLogs,
    handleClearLogs,
    searchQuery,
    setSearchQuery,
    activeFilter,
    setActiveFilter,
    isExpanded,
    setIsExpanded,
    stats,
    filteredLogs
  } = useBatchQueue();

  if (jobQueue.length === 0) return null;

  return (
    <>
      {/* Lista Compacta de Tarefas na Sidebar */}
      <div className="queue-container">
        {completedJobs.length > 0 && (
          <div className="queue-header-actions">
            <button 
              onClick={clearCompletedJobs}
              className="queue-btn-icon"
              title="Limpar tarefas concluídas"
            >
              Limpar <X size={12} />
            </button>
          </div>
        )}

        <div className="queue-job-list">
          {jobQueue.map(job => (
            <div key={job.id} className="queue-job-card">
              <div className="queue-job-top">
                <div className="queue-job-name" title={job.payload?.chapterName || job.page || 'Arquivo'}>
                  {job.payload?.chapterName || job.page || 'Arquivo'}
                </div>
                
                <div className="queue-job-actions">
                  <button 
                    onClick={() => setLogModalJobId(job.id)}
                    className="queue-btn-icon"
                    title="Abrir Console de Telemetria"
                  >
                    <Terminal size={13} />
                  </button>
                  {job.status === 'running' && (
                    <button 
                      onClick={() => handleCancelJob(job.id, false)}
                      className="queue-btn-icon danger"
                      title="Interromper"
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
              </div>
              
              <div className="queue-job-meta">
                <span className={`queue-status-text ${job.status}`}>
                  {job.status === 'running' ? (job.currentStepLabel || 'Processando...') :
                   job.status === 'completed' ? 'Concluído' :
                   job.status === 'cancelled' ? 'Cancelado' :
                   job.status === 'failed' ? 'Erro' : 'Pendente'}
                </span>
                {job.status === 'running' && (
                  <span className="queue-progress-text">
                    {Math.round(Number(job.progress) || 0)}%
                  </span>
                )}
              </div>

              {job.status === 'running' && (
                <div className="queue-progress-track">
                  <div 
                    className="queue-progress-bar" 
                    style={{ width: `${Math.max(2, Math.min(100, Number(job.progress) || 0))}%` }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* DRAWER LATERAL: CONSOLE DE TELEMETRIA TÉCNICA */}
      <QueueTerminalModal
        logModalJob={logModalJob}
        setLogModalJobId={setLogModalJobId}
        isExpanded={isExpanded}
        setIsExpanded={setIsExpanded}
        copied={copied}
        handleCopyLogs={handleCopyLogs}
        handleClearLogs={handleClearLogs}
        stats={stats}
        activeFilter={activeFilter}
        setActiveFilter={setActiveFilter}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        autoScroll={autoScroll}
        setAutoScroll={setAutoScroll}
        logContainerRef={logContainerRef}
        handleLogScroll={handleLogScroll}
        filteredLogs={filteredLogs}
      />
    </>
  );
}