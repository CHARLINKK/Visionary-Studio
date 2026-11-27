import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CanvasErrorBoundary } from '../CanvasErrorBoundary';

const FaultyCanvas = ({ shouldFail }) => {
  if (shouldFail) {
    throw new Error('Konva Render Pipeline Failure: NaN coordinates');
  }
  return <div data-testid="healthy-canvas">Canvas Stage Rendered OK</div>;
};

describe('CanvasErrorBoundary', () => {
  it('renders children smoothly when no error occurs', () => {
    render(
      <CanvasErrorBoundary>
        <FaultyCanvas shouldFail={false} />
      </CanvasErrorBoundary>
    );

    expect(screen.getByTestId('healthy-canvas')).toBeInTheDocument();
    expect(screen.queryByTestId('canvas-error-boundary')).not.toBeInTheDocument();
  });

  it('catches runtime rendering exceptions and presents fallback UI with error details', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onErrorSpy = vi.fn();

    render(
      <CanvasErrorBoundary onError={onErrorSpy}>
        <FaultyCanvas shouldFail={true} />
      </CanvasErrorBoundary>
    );

    expect(screen.getByTestId('canvas-error-boundary')).toBeInTheDocument();
    expect(screen.getByText('Falha na Renderização do Canvas')).toBeInTheDocument();
    expect(onErrorSpy).toHaveBeenCalledTimes(1);

    // Toggle details
    const toggleButton = screen.getByText('Ver Detalhes');
    fireEvent.click(toggleButton);
    expect(screen.getByText(/Konva Render Pipeline Failure/)).toBeInTheDocument();
    expect(screen.getByText('Ocultar Detalhes')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('triggers onReset callback and restores when error condition is resolved', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onResetSpy = vi.fn();

    const TestHost = () => {
      const [shouldFail, setShouldFail] = React.useState(true);
      return (
        <div>
          <button data-testid="fix-error-btn" onClick={() => setShouldFail(false)}>
            Resolver Erro
          </button>
          <CanvasErrorBoundary onReset={onResetSpy}>
            <FaultyCanvas shouldFail={shouldFail} />
          </CanvasErrorBoundary>
        </div>
      );
    };

    render(<TestHost />);

    expect(screen.getByTestId('canvas-error-boundary')).toBeInTheDocument();

    // User fixes the underlying error condition
    fireEvent.click(screen.getByTestId('fix-error-btn'));

    // Click retry on error boundary
    const retryButton = screen.getByText('Tentar Novamente');
    fireEvent.click(retryButton);

    expect(onResetSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('healthy-canvas')).toBeInTheDocument();
    expect(screen.queryByTestId('canvas-error-boundary')).not.toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('automatically resets when resetKeys change', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const TestHostWithKeys = () => {
      const [pageId, setPageId] = React.useState('page-1');
      return (
        <div>
          <button data-testid="change-page-btn" onClick={() => setPageId('page-2')}>
            Trocar Pagina
          </button>
          <CanvasErrorBoundary resetKeys={[pageId]}>
            <FaultyCanvas shouldFail={pageId === 'page-1'} />
          </CanvasErrorBoundary>
        </div>
      );
    };

    render(<TestHostWithKeys />);
    expect(screen.getByTestId('canvas-error-boundary')).toBeInTheDocument();

    // Change page key
    fireEvent.click(screen.getByTestId('change-page-btn'));

    expect(screen.getByTestId('healthy-canvas')).toBeInTheDocument();
    expect(screen.queryByTestId('canvas-error-boundary')).not.toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
