import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

/**
 * CanvasErrorBoundary
 *
 * Captura exceções em tempo de execução no motor Konva ou na manipulação de
 * imagens e coordenadas da página, prevenindo a quebra completa do editor e
 * fornecendo recuperação isolada sem perda de dados na interface.
 */
export class CanvasErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, showDetails: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[CanvasErrorBoundary] Falha capturada no Canvas:', error, errorInfo);
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  componentDidUpdate(prevProps) {
    // Se resetKeys mudarem (ex: troca de página ou reset externo), limpa o erro
    if (this.state.hasError && this.props.resetKeys && prevProps.resetKeys) {
      const hasChanged = this.props.resetKeys.some(
        (key, idx) => key !== prevProps.resetKeys[idx]
      );
      if (hasChanged) {
        this.handleReset();
      }
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, showDetails: false });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="canvas-container canvas-error-fallback"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            width: '100%',
            backgroundColor: 'var(--bg-main, #0f1117)',
            color: 'var(--text-main, #e2e8f0)',
            padding: '24px',
            textAlign: 'center',
            userSelect: 'none',
          }}
          data-testid="canvas-error-boundary"
        >
          <div
            style={{
              background: 'var(--bg-card, rgba(30, 41, 59, 0.5))',
              border: '1px solid var(--border-subtle, rgba(239, 68, 68, 0.25))',
              borderRadius: '12px',
              padding: '32px 24px',
              maxWidth: '520px',
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '16px',
              boxShadow: '0 10px 30px rgba(0, 0, 0, 0.15)',
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                background: 'rgba(239, 68, 68, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ef4444',
              }}
            >
              <AlertTriangle size={24} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-main, #f87171)' }}>
                Falha na Renderização do Canvas
              </h3>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted, #94a3b8)', lineHeight: 1.5 }}>
                Ocorreu um erro ao renderizar os gráficos ou a imagem da página. Os dados salvos continuam protegidos.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
              <button
                type="button"
                onClick={this.handleReset}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: 'var(--accent, #3b82f6)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '8px 16px',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                <RefreshCw size={14} />
                Tentar Novamente
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
                  border: '1px solid var(--border-subtle, #334155)',
                  borderRadius: '6px',
                  padding: '8px 14px',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                }}
              >
                {this.state.showDetails ? 'Ocultar Detalhes' : 'Ver Detalhes'}
              </button>
            </div>

            {this.state.showDetails && (
              <pre
                style={{
                  margin: '12px 0 0 0',
                  padding: '12px',
                  background: 'var(--bg-main, #090d16)',
                  border: '1px solid var(--border-subtle, #1e293b)',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  color: '#fca5a5',
                  textAlign: 'left',
                  width: '100%',
                  maxHeight: '160px',
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

export default CanvasErrorBoundary;
