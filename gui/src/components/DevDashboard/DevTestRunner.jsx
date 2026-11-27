import React from 'react';
import { Play, RefreshCw, CheckCircle, Check, X } from 'lucide-react';

export default function DevTestRunner({
  testFiles,
  selectedTest,
  setSelectedTest,
  isRunningTest,
  handleRunTests,
  handleCancelTests,
  testProgress
}) {
  return (
    <>
      {/* ── Barra de Progresso Visual dos Testes (em tempo real) ── */}
      {(isRunningTest || testProgress.percent > 0) && (
        <div className="test-progress-banner">
          <div className="test-progress-header">
            <div className="test-progress-title">
              {isRunningTest ? (
                <>
                  <RefreshCw size={14} className="spin" />
                  <span>Executando Diagnóstico Automatizado...</span>
                </>
              ) : (
                <>
                  <CheckCircle size={14} color="var(--brand-primary)" />
                  <span>Diagnóstico Concluído</span>
                </>
              )}
            </div>

            <div className="test-progress-badges">
              <span className="test-badge passed">
                <Check size={11} /> {testProgress.passed} PASSANDO
              </span>
              {testProgress.failed > 0 && (
                <span className="test-badge failed">
                  <X size={11} /> {testProgress.failed} FALHAS
                </span>
              )}
              {testProgress.skipped > 0 && (
                <span className="test-badge skipped">
                  {testProgress.skipped} PULADOS
                </span>
              )}
              <span className="test-badge pct">{testProgress.percent}%</span>
            </div>
          </div>

          <div className="test-progress-bar-track">
            <div 
              className={`test-progress-bar-fill ${testProgress.failed > 0 ? 'has-failures' : ''}`}
              style={{ width: `${testProgress.percent}%` }}
            />
          </div>

          {testProgress.current_test && (
            <div className="test-current-line">
              <span className="test-current-tag">TESTE ATUAL:</span> {testProgress.current_test}
            </div>
          )}
        </div>
      )}

      {/* ── Controles de Execução de Testes ── */}
      <div className="test-controls">
        <select 
          value={selectedTest} 
          onChange={(e) => setSelectedTest(e.target.value)}
          disabled={isRunningTest}
          className="test-selector"
        >
          {testFiles.map(file => (
            <option key={file.filename} value={file.filename}>
              {file.label}
            </option>
          ))}
        </select>
        <button 
          className="run-test-btn" 
          onClick={handleRunTests} 
          disabled={isRunningTest}
        >
          {isRunningTest ? <><RefreshCw size={14} className="spin"/> Testando...</> : <><Play size={14}/> Executar Teste</>}
        </button>
        {isRunningTest && (
          <button 
            className="cancel-test-btn" 
            onClick={handleCancelTests} 
            title="Interromper execução do diagnóstico"
          >
            <X size={14} /> Cancelar
          </button>
        )}
      </div>
    </>
  );
}
