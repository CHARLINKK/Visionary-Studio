import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ConfirmModal from '../ConfirmModal';

describe('ConfirmModal component', () => {
  it('should not render anything when isOpen is false', () => {
    const { container } = render(
      <ConfirmModal isOpen={false} onConfirm={vi.fn()} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('should render title, message, and action buttons when open', () => {
    render(
      <ConfirmModal
        isOpen={true}
        title="Deseja excluir?"
        message="Esta ação é irreversível."
        confirmText="Sim, excluir"
        cancelText="Voltar"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('Deseja excluir?')).toBeInTheDocument();
    expect(screen.getByText('Esta ação é irreversível.')).toBeInTheDocument();
    expect(screen.getByText('Sim, excluir')).toBeInTheDocument();
    expect(screen.getByText('Voltar')).toBeInTheDocument();
  });

  it('should call onConfirm when clicking confirm button or pressing Enter', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();

    render(
      <ConfirmModal
        isOpen={true}
        confirmText="Confirmar"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );

    fireEvent.click(screen.getByText('Confirmar'));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: 'Enter' });
    expect(onConfirm).toHaveBeenCalledTimes(2);
  });

  it('should call onClose when clicking cancel or pressing Escape', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();

    render(
      <ConfirmModal
        isOpen={true}
        cancelText="Cancelar"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );

    fireEvent.click(screen.getByText('Cancelar'));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
