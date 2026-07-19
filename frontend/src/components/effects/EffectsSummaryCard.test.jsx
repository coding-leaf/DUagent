import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import EffectsSummaryCard from './EffectsSummaryCard';

describe('EffectsSummaryCard', () => {
  it('requires an explicit click before opening personalized generation', () => {
    const onGenerateResources = vi.fn();
    render(
      <EffectsSummaryCard
        summaryText="指针仍需复习"
        loading={false}
        onGenerateResources={onGenerateResources}
      />,
    );

    expect(onGenerateResources).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '根据学情生成资料' }));
    expect(onGenerateResources).toHaveBeenCalledTimes(1);
  });
});
