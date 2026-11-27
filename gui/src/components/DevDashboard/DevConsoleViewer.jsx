import React from 'react';
import { 
  Terminal, ShieldCheck, Radio, Copy, Trash2, Search, X 
} from 'lucide-react';

export default function DevConsoleViewer({
  activeConsole,
  setActiveConsole,
  isRunningTest,
  events,
  testProgress,
  handleCopyLogs,
  handleClearCurrentLogs,
  logSearch,
  setLogSearch,
  logFilter,
  setLogFilter,
  filteredLogs,
  consoleRef,
  setAutoScroll
}) {
  return (
    <>
      <div className="console-tabs">
        <button 
          className={`console-tab ${activeConsole === 'app' ? 'active' : ''}`}
          onClick={() => setActiveConsole('app')}
        >
          <Terminal size={14} /> Terminal da Aplicação
        </button>
        <button 
          className={`console-tab ${activeConsole === 'test' ? 'active' : ''}`}
          onClick={() => setActiveConsole('test')}
        >
          <ShieldCheck size={14} /> Terminal do Pytest
          {isRunningTest && <span className="running-dot" />}
        </button>
        <button 
          className={`console-tab ${activeConsole === 'events' ? 'active' : ''}`}
          onClick={() => setActiveConsole('events')}
        >
          <Radio size={14} /> EventBus Spy
          {events.length > 0 && <span className="events-count-pill">{events.length}</span>}
        </button>
      </div>

      {/* ── Janela do Console com Barra de Busca e Filtros ── */}
      <div className="dev-console-window">
        <div className="console-titlebar">
          <div className="dots">
            <span className="dot red" />
            <span className="dot yellow" />
            <span className="dot green" />
          </div>
          
          <div className="title">
            {activeConsole === 'test' ? `bash - pytest tests/${testProgress.total ? ` (${testProgress.total} testes)` : ''}` : 
             activeConsole === 'events' ? 'eventbus - pub/sub runtime channel monitor' : 
             'core - visionary-studio/backend stream'}
          </div>

          <div className="console-actions">
            <button className="copy-btn" onClick={handleCopyLogs} title="Copiar conteúdo"><Copy size={14}/></button>
            <button className="copy-btn" onClick={handleClearCurrentLogs} title="Limpar visualização local"><Trash2 size={14}/></button>
          </div>
        </div>

        {/* Barra de Filtros e Busca do Console */}
        {activeConsole !== 'events' && (
          <div className="console-toolbar">
            <div className="search-box">
              <Search size={13} className="search-icon" />
              <input 
                type="text" 
                placeholder="Buscar no log..." 
                value={logSearch}
                onChange={(e) => setLogSearch(e.target.value)}
                className="console-search-input"
              />
              {logSearch && (
                <button className="search-clear-btn" onClick={() => setLogSearch('')}>
                  <X size={12} />
                </button>
              )}
            </div>

            <div className="filter-pills">
              <button 
                className={`filter-pill ${logFilter === 'all' ? 'active' : ''}`}
                onClick={() => setLogFilter('all')}
              >
                Todos
              </button>
              <button 
                className={`filter-pill error ${logFilter === 'error' ? 'active' : ''}`}
                onClick={() => setLogFilter('error')}
              >
                Erros
              </button>
              <button 
                className={`filter-pill warning ${logFilter === 'warning' ? 'active' : ''}`}
                onClick={() => setLogFilter('warning')}
              >
                Avisos
              </button>
              <button 
                className={`filter-pill success ${logFilter === 'success' ? 'active' : ''}`}
                onClick={() => setLogFilter('success')}
              >
                Sucesso
              </button>
            </div>

            <div className="logs-meta-count">
              <span>{filteredLogs.length} linhas</span>
            </div>
          </div>
        )}

        {/* Corpo do Console: Terminal de Logs */}
        {activeConsole !== 'events' ? (
          <div 
            className="console-body" 
            ref={consoleRef}
            onScroll={(e) => {
              const el = e.target;
              const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 15;
              setAutoScroll(isAtBottom);
            }}
          >
            {filteredLogs.length === 0 ? (
              <div className="console-placeholder">
                {logSearch || logFilter !== 'all' ? 'Nenhum log encontrado para o filtro aplicado.' : 'Nenhum log disponível no momento.'}
              </div>
            ) : (
              filteredLogs.map((log, index) => {
                let color = '#a3a3a3';
                if (log.includes('PASSED') || log.includes('SUCESSO')) color = '#ffffff';
                if (log.includes('FAILED') || log.includes('ERROR') || log.includes('FALHAS') || log.includes('[ERRO]')) {
                  color = '#f87171';
                }
                if (log.includes('WARNING') || log.includes('SKIPPED') || log.includes('[DEV]')) color = '#fbbf24';
                if (log.includes('>>>')) color = '#e4e4e7';
                
                return (
                  <div key={index} className="log-line" style={{ color }}>
                    <span>{log}</span>
                  </div>
                );
              })
            )}
          </div>
        ) : (
          /* Corpo do Console: EventBus Spy */
          <div className="eventbus-body">
            {events.length === 0 ? (
              <div className="console-placeholder">
                Aguardando eventos do sistema (EventBus)... Dispare uma ação no Visionary para ver o tráfego em tempo real.
              </div>
            ) : (
              <div className="events-feed">
                {events.map((evt) => (
                  <div key={evt.id} className="event-item">
                    <div className="event-header">
                      <span className="event-time">{evt.time}</span>
                      <span className="event-tag">{evt.name}</span>
                    </div>
                    {evt.payload && (
                      <pre className="event-payload">
                        {typeof evt.payload === 'object' ? JSON.stringify(evt.payload, null, 2) : String(evt.payload)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
