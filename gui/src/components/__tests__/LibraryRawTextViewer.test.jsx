import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LibraryRawTextViewer from '../Library/LibraryRawTextViewer';

describe('LibraryRawTextViewer Component', () => {
  it('renders empty message when content is empty or null', () => {
    render(<LibraryRawTextViewer content="" />);
    expect(screen.getByText('Nenhum conteúdo disponível.')).toBeInTheDocument();
  });

  it('renders minimalist syntax highlighted tokens and clickable text [id: X]', () => {
    const fakeContent = [
      '# VISIONARY STUDIO - ROTEIRO DE TRADUCAO',
      '# CAPITULO: Chapter 001',
      '==================================================',
      'PAGINA 1: 001.JPG',
      '==================================================',
      '',
      '# [id: 1]',
      '[EN]: Hello world!',
      '[BR]: [PENDENTE]',
      '',
      '# [id: 2]',
      '[EN]: Good morning!',
      '[BR]: Bom dia!',
    ].join('\n');

    const handleSelectBalloon = vi.fn();

    render(<LibraryRawTextViewer content={fakeContent} onSelectBalloon={handleSelectBalloon} />);

    // Brand and Chapter metadata
    expect(screen.getByText(/ROTEIRO DE TRADUCAO/)).toBeInTheDocument();
    expect(screen.getByText('Chapter 001')).toBeInTheDocument();

    // Page header (clean text, no extra jump button)
    expect(screen.getByText(/PAGINA 1/)).toBeInTheDocument();

    // Balloon 1 text link: [id: 1]
    const balloon1Link = screen.getByText('[id: 1]');
    expect(balloon1Link).toBeInTheDocument();
    expect(balloon1Link).toHaveClass('token-id-link');
    expect(balloon1Link).toHaveAttribute('title', 'Abrir Pág. 1, Balão #1 no modo Lado a Lado');

    // Clicking [id: 1] text triggers callback with pageNumber: 1, balloonId: '1'
    fireEvent.click(balloon1Link);
    expect(handleSelectBalloon).toHaveBeenCalledWith(1, '1');

    // Balloon 2 text link: [id: 2]
    const balloon2Link = screen.getByText('[id: 2]');
    expect(balloon2Link).toBeInTheDocument();
    expect(balloon2Link).toHaveClass('token-id-link');
    fireEvent.click(balloon2Link);
    expect(handleSelectBalloon).toHaveBeenCalledWith(1, '2');
  });
});
