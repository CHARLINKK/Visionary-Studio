import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CanvasContextMenu } from '../canvas/CanvasContextMenu';

describe('CanvasContextMenu Component', () => {
  const dummyBubble = {
    id: 'b1',
    order: 1,
    x1: 100,
    y1: 100,
    x2: 220,
    y2: 180,
    is_sfx: false,
    text: 'Hello world',
  };

  const dummyBoxes = [dummyBubble];

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <CanvasContextMenu
        isOpen={false}
        x={100}
        y={100}
        targetBubble={dummyBubble}
        boxes={dummyBoxes}
        onClose={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  describe('When right-clicking on a balloon (targetBubble provided)', () => {
    it('renders balloon info and actions', () => {
      render(
        <CanvasContextMenu
          isOpen={true}
          x={150}
          y={150}
          targetBubble={dummyBubble}
          boxes={dummyBoxes}
          onClose={vi.fn()}
        />
      );

      expect(screen.getByText(/Balão de Diálogo/i)).toBeInTheDocument();
      expect(screen.getByText(/120×80px/i)).toBeInTheDocument();
      expect(screen.getByText(/Converter em SFX/i)).toBeInTheDocument();
      expect(screen.getByText(/Expandir Margem \(\+6px\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Encolher Margem \(-6px\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Editar Nós do Polígono/i)).toBeInTheDocument();
      expect(screen.getByText(/Excluir Balão/i)).toBeInTheDocument();
    });

    it('triggers toggleSfx when clicking on toggle SFX action', () => {
      const mockToggleSfx = vi.fn();
      const mockClose = vi.fn();

      render(
        <CanvasContextMenu
          isOpen={true}
          x={150}
          y={150}
          targetBubble={dummyBubble}
          boxes={dummyBoxes}
          actions={{ toggleSfx: mockToggleSfx }}
          onClose={mockClose}
        />
      );

      fireEvent.click(screen.getByText(/Converter em SFX/i));
      expect(mockToggleSfx).toHaveBeenCalledWith('b1');
      expect(mockClose).toHaveBeenCalled();
    });

    it('triggers inflateMargin when clicking expand or shrink margin', () => {
      const mockInflate = vi.fn();
      const mockClose = vi.fn();

      render(
        <CanvasContextMenu
          isOpen={true}
          x={150}
          y={150}
          targetBubble={dummyBubble}
          boxes={dummyBoxes}
          actions={{ inflateMargin: mockInflate }}
          onClose={mockClose}
        />
      );

      fireEvent.click(screen.getByText(/Expandir Margem \(\+6px\)/i));
      expect(mockInflate).toHaveBeenCalledWith('b1', 6);
      expect(mockClose).toHaveBeenCalled();

      fireEvent.click(screen.getByText(/Encolher Margem \(-6px\)/i));
      expect(mockInflate).toHaveBeenCalledWith('b1', -6);
    });

    it('triggers delete when clicking delete action', () => {
      const mockDelete = vi.fn();
      const mockClose = vi.fn();

      render(
        <CanvasContextMenu
          isOpen={true}
          x={150}
          y={150}
          targetBubble={dummyBubble}
          boxes={dummyBoxes}
          actions={{ delete: mockDelete }}
          onClose={mockClose}
        />
      );

      fireEvent.click(screen.getByText(/Excluir Balão/i));
      expect(mockDelete).toHaveBeenCalledWith('b1');
      expect(mockClose).toHaveBeenCalled();
    });
  });

  describe('When right-clicking on empty canvas (targetBubble is null)', () => {
    it('renders canvas shortcuts and drawing tools', () => {
      render(
        <CanvasContextMenu
          isOpen={true}
          x={200}
          y={200}
          targetBubble={null}
          boxes={dummyBoxes}
          pageIndex={0}
          totalPages={10}
          onClose={vi.fn()}
        />
      );

      expect(screen.getByText(/Canvas • Pág\. 1 \/ 10/i)).toBeInTheDocument();
      expect(screen.getByText(/Criar Balão Retangular/i)).toBeInTheDocument();
      expect(screen.getByText(/Desenhar com Caneta/i)).toBeInTheDocument();
      expect(screen.getByText(/Auto-Ordenar Mangá/i)).toBeInTheDocument();
      expect(screen.getByText(/Marcar Ordem 1-a-1/i)).toBeInTheDocument();
      expect(screen.getByText(/Enquadrar Página na Tela/i)).toBeInTheDocument();
    });

    it('activates rect and pen tools from menu', () => {
      const mockSetActiveTool = vi.fn();
      const mockClose = vi.fn();

      render(
        <CanvasContextMenu
          isOpen={true}
          x={200}
          y={200}
          targetBubble={null}
          boxes={dummyBoxes}
          setActiveTool={mockSetActiveTool}
          onClose={mockClose}
        />
      );

      fireEvent.click(screen.getByText(/Criar Balão Retangular/i));
      expect(mockSetActiveTool).toHaveBeenCalledWith('rect');
      expect(mockClose).toHaveBeenCalled();

      fireEvent.click(screen.getByText(/Desenhar com Caneta/i));
      expect(mockSetActiveTool).toHaveBeenCalledWith('pen');
    });

    it('triggers fitToScreen when clicking enquadrar página', () => {
      const mockFit = vi.fn();
      const mockClose = vi.fn();

      render(
        <CanvasContextMenu
          isOpen={true}
          x={200}
          y={200}
          targetBubble={null}
          boxes={dummyBoxes}
          fitToScreen={mockFit}
          onClose={mockClose}
        />
      );

      fireEvent.click(screen.getByText(/Enquadrar Página na Tela/i));
      expect(mockFit).toHaveBeenCalled();
      expect(mockClose).toHaveBeenCalled();
    });
  });

  describe('Closing interactions', () => {
    it('closes on Escape key press', () => {
      const mockClose = vi.fn();
      render(
        <CanvasContextMenu
          isOpen={true}
          x={200}
          y={200}
          targetBubble={null}
          boxes={dummyBoxes}
          onClose={mockClose}
        />
      );

      fireEvent.keyDown(window, { key: 'Escape' });
      expect(mockClose).toHaveBeenCalled();
    });

    it('closes on mouse wheel event (pan/zoom)', () => {
      const mockClose = vi.fn();
      render(
        <CanvasContextMenu
          isOpen={true}
          x={200}
          y={200}
          targetBubble={null}
          boxes={dummyBoxes}
          onClose={mockClose}
        />
      );

      fireEvent.wheel(window);
      expect(mockClose).toHaveBeenCalled();
    });
  });
});
