import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '../ErrorBoundary';

const ProblemChild = ({ shouldThrow }) => {
  if (shouldThrow) {
    throw new Error('Explosão de renderização simulada');
  }
  return <div>Filho Saudável</div>;
};

describe('ErrorBoundary component', () => {
  it('should render children when there is no runtime error', () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Filho Saudável')).toBeInTheDocument();
  });

  it('should catch child errors and display crash fallback screen', () => {
    // Suppress console.error output from React's internal error boundary logging during test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('React Crash!')).toBeInTheDocument();
    expect(screen.getAllByText(/Explosão de renderização simulada/).length).toBeGreaterThanOrEqual(1);

    consoleSpy.mockRestore();
  });
});
