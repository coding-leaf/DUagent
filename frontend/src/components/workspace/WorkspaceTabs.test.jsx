import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import WorkspaceTabs from './WorkspaceTabs';

describe('WorkspaceTabs', () => {
  it('renders PersonalizedResourceCard title and icon from pluginMeta', () => {
    const artifacts = [
      { id: 'res-1', type: 'PersonalizedResourceCard' }
    ];
    const { container } = render(
      <WorkspaceTabs
        artifacts={artifacts}
        activeId="res-1"
        onSelect={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('个性化资源')).toBeDefined();
    expect(container.querySelector('.lucide-book-open')).not.toBeNull();
  });

  it('allows selecting a tab', () => {
    const onSelect = vi.fn();
    const artifacts = [
      { id: '1', type: 'QuizCard' },
      { id: '2', type: 'PersonalizedResourceCard' }
    ];
    render(
      <WorkspaceTabs
        artifacts={artifacts}
        activeId="1"
        onSelect={onSelect}
        onClose={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText('个性化资源'));
    expect(onSelect).toHaveBeenCalledWith('2');
  });

  it('renders hidden artifacts dropdown and restores', () => {
    const onRestore = vi.fn();
    const hiddenArtifacts = [
      { id: 'h-1', type: 'PersonalizedResourceCard' }
    ];
    render(
      <WorkspaceTabs
        artifacts={[]}
        activeId={null}
        onSelect={vi.fn()}
        onClose={vi.fn()}
        hiddenArtifacts={hiddenArtifacts}
        onRestore={onRestore}
      />
    );

    const toggleBtn = screen.getByRole('button', { name: /找回已关闭/ });
    fireEvent.click(toggleBtn);
    expect(screen.getByText('个性化资源')).toBeDefined();

    fireEvent.click(screen.getByText('个性化资源'));
    expect(onRestore).toHaveBeenCalledWith('h-1');
  });
});
