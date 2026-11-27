import { Terminal, Lock } from 'lucide-react';
import { DEV_BOOT_LOGS } from '../../hooks/useDevMode';

export function DevModeOverlay({
  devTransition,
  devLoadingFading,
  skipDevLoading,
  devLoadingProgress,
  devUser,
  devLogIndex,
  showPasswordModal,
  setShowPasswordModal,
  handlePasswordSubmit,
  passwordInput,
  setPasswordInput,
  passwordError,
  setPasswordError
}) {
  return (
    <>
      {devTransition === 'loading' && (
        <div 
          className={`dev-loading-screen ${devLoadingFading ? 'fade-out' : ''}`}
          onClick={skipDevLoading}
          style={{ cursor: 'pointer' }}
          title="Clique ou pressione ENTER para pular"
        >
          <div className="dev-loading-cyber-grid" />
          <div className="dev-loading-scanline" />
          
          <div className="dev-loading-content">
            <div className="dev-loading-icon-wrapper">
              <div className="dev-loading-pulse-ring" />
              <div className="dev-loading-pulse-ring delay" />
              <Terminal size={42} className="dev-loading-icon" />
            </div>

            <div className="dev-loading-header">
              <span className="dev-loading-badge">SYSTEM PRIVILEGE ESCALATION // LEVEL 0</span>
              <h2 className="dev-loading-title">VISIONARY <span className="highlight">DEV CORE</span></h2>
              {devLoadingProgress === 100 && devUser && (
                <div className="dev-loading-welcome-banner">
                  <span className="dev-welcome-prefix">BEM-VINDO</span>
                  <span className="dev-welcome-name">{devUser}</span>
                </div>
              )}
            </div>

            <div className="dev-loading-bar-container">
              <div className="dev-loading-bar-track">
                <div 
                  className="dev-loading-bar-fill" 
                  style={{ width: `${devLoadingProgress}%` }}
                />
              </div>
              <div className="dev-loading-bar-meta">
                <span className="dev-loading-status-text">
                  {devLoadingProgress < 100 
                    ? 'INICIALIZANDO SUBSISTEMAS...' 
                    : (devUser ? `ACESSO CONCEDIDO // BEM-VINDO, ${devUser}` : 'ACESSO CONCEDIDO // PROTOCOLO PRONTO')}
                </span>
                <span className="dev-loading-pct">{devLoadingProgress}%</span>
              </div>
            </div>

            <div className="dev-loading-terminal">
              {DEV_BOOT_LOGS(devUser || 'DEVELOPER').slice(0, devLogIndex + 1).map((log, idx) => (
                <div key={idx} className={`dev-loading-log-line ${idx === 4 ? 'dev-log-welcome' : ''}`}>
                  <span className="log-prompt">&gt;</span> {log}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {showPasswordModal && (
        <div className="dev-pwd-overlay" onClick={() => setShowPasswordModal(false)}>
          <div className="dev-pwd-modal" onClick={(e) => e.stopPropagation()}>
            <div className="dev-pwd-header">
              <Lock size={18} color="var(--brand-primary)" />
              <h3>Desbloquear Modo Desenvolvedor</h3>
            </div>
            <p>Digite a senha secreta de desenvolvedor para acessar a central de testes e diagnóstico:</p>
            <form onSubmit={handlePasswordSubmit}>
              <input
                type="password"
                autoFocus
                className="dev-pwd-input"
                placeholder="Digite a senha..."
                value={passwordInput}
                onChange={(e) => {
                  setPasswordInput(e.target.value);
                  setPasswordError('');
                }}
              />
              {passwordError && <div className="dev-pwd-error">{passwordError}</div>}
              <div className="dev-pwd-actions">
                <button type="button" className="dev-pwd-btn" onClick={() => setShowPasswordModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="dev-pwd-btn confirm">
                  Desbloquear
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
