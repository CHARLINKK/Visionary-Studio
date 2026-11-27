import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LibraryBalloonRow from '../Library/LibraryBalloonRow';

describe('LibraryBalloonRow Component', () => {
  const fakePage = {
    pageNumber: 1,
    pageName: '001.JPG',
    balloons: [
      { id: '1', en: 'First dialogue', br: 'Primeiro diálogo' },
      { id: '2', en: 'Second dialogue', br: 'Segundo diálogo' },
    ],
  };

  it('invokes onJumpToSplit with exact page and balloon index when clicking the number badge in script mode', () => {
    const handleJumpToSplit = vi.fn();
    const handleCopyBalloon = vi.fn();

    render(
      <LibraryBalloonRow
        pageData={fakePage}
        balloonData={fakePage.balloons[1]}
        bIdx={1}
        isSplitMode={false}
        activeTab={null}
        setActiveTab={vi.fn()}
        isSearchMatch={false}
        isSearchActive={false}
        copyBalloon={handleCopyBalloon}
        undoCopyBalloon={vi.fn()}
        saveBalloonText={vi.fn()}
        onJumpToSplit={handleJumpToSplit}
      />
    );

    // Number badge shows #2
    const numBadge = screen.getByText('#2');
    expect(numBadge).toBeInTheDocument();

    // Clicking the badge must trigger onJumpToSplit with page: 1, bIdx: 1, id: '2'
    fireEvent.click(numBadge);
    expect(handleJumpToSplit).toHaveBeenCalledTimes(1);
    expect(handleJumpToSplit).toHaveBeenCalledWith(1, 1, '2');

    // copyBalloon must not be triggered when clicking the badge
    expect(handleCopyBalloon).not.toHaveBeenCalled();
  });
});
