import React from 'react';
import { AlertTriangle, RefreshCw, Copy, Check } from 'lucide-react';

/**
 * ErrorBoundary Component
 *
 * Capturador global de exceções da aplicação React.
 * Oferece interface resiliente e compatível com todos os temas do Visionary Studio,
 * permitindo recarregar o aplicativo e copiar dados de diagnóstico.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, copied: false, showDetails: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Falha capturada na interface:', error, errorInfo);
  }

  handleReload = () => {
    if (typeof window !== 'undefined' && window.location) {
      window.location.reload();
    }
  };

  handleCopy = () => {
    const errorText = `${this.state.error?.toString() || ''}\n\n${this.state.error?.stack || ''}`;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(errorText);
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2000);
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          data-testid="app-error-boundary"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 99999,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'var(--bg-main, #0f1117)',
            color: 'var(--text-main, #e2e8f0)',
            padding: '24px',
            fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
            userSelect: 'none',
          }}
        >
          <div
            style={{
              background: 'var(--bg-card, rgba(30, 41, 59, 0.5))',
              border: '1px solid var(--border-subtle, rgba(239, 68, 68, 0.25))',
              borderRadius: '14px',
              padding: '36px 32px',
              maxWidth: '560px',
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25)',
              gap: '20px',
            }}
          >
            <div
              style={{
                width: '54px',
                height: '54px',
                borderRadius: '50%',
                background: 'rgba(239, 68, 68, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ef4444',
              }}
            >
              <AlertTriangle size={28} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h2
                style={{
                  margin: 0,
                  fontSize: '1.25rem',
                  fontWeight: 600,
                  color: 'var(--text-main, #f87171)',
                  letterSpacing: '-0.02em',
                }}
              >
                React Crash!
              </h2>
              <p
                style={{
                  margin: 0,
                  fontSize: '0.875rem',
                  color: 'var(--text-muted, #94a3b8)',
                  lineHeight: 1.5,
                }}
              >
                Ocorreu uma exceção não tratada na renderização da interface. Seus arquivos e projetos salvos no disco continuam protegidos.
              </p>
            </div>

            <div
              style={{
                padding: '8px 12px',
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                borderRadius: '6px',
                fontSize: '0.8rem',
                color: '#f87171',
                maxWidth: '100%',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontFamily: 'monospace',
              }}
            >
              {this.state.error?.message || this.state.error?.toString() || 'Erro desconhecido'}
            </div>

            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
              <button
                type="button"
                onClick={this.handleReload}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: 'var(--accent, #3b82f6)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '9px 18px',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'opacity 0.2s',
                }}
              >
                <RefreshCw size={15} />
                Recarregar Aplicativo
              </button>

              <button
                type="button"
                onClick={this.handleCopy}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: 'transparent',
                  color: 'var(--text-main, #e2e8f0)',
                  border: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.15))',
                  borderRadius: '8px',
                  padding: '9px 16px',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                {this.state.copied ? <Check size={15} style={{ color: '#22c55e' }} /> : <Copy size={15} />}
                {this.state.copied ? 'Copiado!' : 'Copiar Diagnóstico'}
              </button>

              <button
                type="button"
                onClick={() => this.setState((prev) => ({ showDetails: !prev.showDetails }))}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  backgroundColor: 'transparent',
                  color: 'var(--text-muted, #94a3b8)',
                  border: 'none',
                  padding: '9px 12px',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  textUnderlineOffset: '3px',
                }}
              >
                {this.state.showDetails ? 'Ocultar Detalhes' : 'Ver Detalhes'}
              </button>
            </div>

            {this.state.showDetails && (
              <pre
                style={{
                  margin: 0,
                  padding: '14px',
                  background: 'var(--bg-main, #0b0f19)',
                  border: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.1))',
                  borderRadius: '8px',
                  fontSize: '0.75rem',
                  color: '#fca5a5',
                  textAlign: 'left',
                  width: '100%',
                  maxHeight: '180px',
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'monospace',
                }}
              >
                {this.state.error?.toString() || 'Erro desconhecido'}
                {this.state.error?.stack ? `\n\n${this.state.error.stack}` : ''}
              </pre>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
