import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import TranslationModelsGrid from '../ModulesCenter/TranslationModelsGrid';

describe('TranslationModelsGrid (Amadeus Verbo Exclusivity)', () => {
  const mockPull = vi.fn();
  const mockDelete = vi.fn();
  const mockCancel = vi.fn();
  const mockSetUserSettings = vi.fn();

  const defaultProps = {
    ollamaModels: ['amadeus:14b'],
    ollamaModelsDetails: {
      'amadeus:14b': { sizeFormatted: '9.0 GB' },
    },
    ollamaModelsTags: {},
    userSettings: {
      transPol: 'amadeus:14b',
    },
    setUserSettings: mockSetUserSettings,
    hardwareStats: {
      vram_reserved_gb: 8.0,
      ram_total_gb: 32.0,
    },
    pullOllamaModel: mockPull,
    deleteOllamaModel: mockDelete,
    cancelOllamaDownload: mockCancel,
  };

  it('renders recommended models containing only the Amadeus Verbo family (7B, 14B, 32B)', () => {
    const { container } = render(<TranslationModelsGrid {...defaultProps} />);
    const grid = container.querySelector('.native-models-grid');

    expect(within(grid).getByText('Amadeus Verbo (14B)')).toBeInTheDocument();
    expect(within(grid).getByText('Amadeus Verbo (7B)')).toBeInTheDocument();
    expect(within(grid).getByText('Amadeus Verbo (32B)')).toBeInTheDocument();

    // Base Qwen and DeepSeek are removed
    expect(within(grid).queryByText('Qwen 2.5 (7B)')).not.toBeInTheDocument();
    expect(within(grid).queryByText('Qwen 2.5 (14B)')).not.toBeInTheDocument();
    expect(within(grid).queryByText('Qwen 2.5 (32B)')).not.toBeInTheDocument();
    expect(within(grid).queryByText('DeepSeek R1 (7B)')).not.toBeInTheDocument();
  });

  it('shows Amadeus 7B as available to pull and triggers pullOllamaModel when clicked', () => {
    const { container } = render(<TranslationModelsGrid {...defaultProps} />);
    const grid = container.querySelector('.native-models-grid');

    // amadeus:7b is not in ollamaModels in defaultProps
    const card = within(grid).getByText('Amadeus Verbo (7B)').closest('.native-model-card');
    expect(card).toBeInTheDocument();

    const downloadBtn = card.querySelector('button.btn-model-action.download');
    expect(downloadBtn).toBeInTheDocument();

    fireEvent.click(downloadBtn);
    expect(mockPull).toHaveBeenCalledWith('amadeus:7b');
  });

  it('filters recommended models properly and keeps Amadeus Verbo visible', () => {
    const { container } = render(<TranslationModelsGrid {...defaultProps} />);
    const grid = container.querySelector('.native-models-grid');

    const recommendedFilterBtn = screen.getByRole('button', { name: /Recomendados/i });
    fireEvent.click(recommendedFilterBtn);

    expect(within(grid).getByText('Amadeus Verbo (14B)')).toBeInTheDocument();
    expect(within(grid).getByText('Amadeus Verbo (7B)')).toBeInTheDocument();
    expect(within(grid).getByText('Amadeus Verbo (32B)')).toBeInTheDocument();
  });

  it('correctly identifies installed vs available status for Amadeus models', () => {
    const { container } = render(<TranslationModelsGrid {...defaultProps} />);
    const grid = container.querySelector('.native-models-grid');

    const card = within(grid).getByText('Amadeus Verbo (14B)').closest('.native-model-card');
    expect(card.querySelector('.badge-installed-tag')).toBeInTheDocument();
    expect(card.className).toContain('installed-model');
  });
});
