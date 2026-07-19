import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ToolCallCard from './ToolCallCard';

describe('ToolCallCard', () => {
  it('renders tool progress details without retry actions', () => {
    render(
      <ToolCallCard
        title="分析薄弱点"
        name="get_weak_points"
        status="completed"
        description="读取画像和最近练习结果"
        outputSummary="识别到 3 个薄弱点"
      />
    );

    expect(screen.getByText('分析薄弱点')).toBeDefined();
    expect(screen.getByText('get_weak_points')).toBeDefined();
    expect(screen.getByText('读取画像和最近练习结果')).toBeDefined();
    expect(screen.getByText(/识别到 3 个薄弱点/)).toBeDefined();
    expect(screen.queryByText('重试')).toBeNull();
  });

  it('renders warning outcomes in yellow', () => {
    const { container } = render(
      <ToolCallCard name="run_code_in_oj" status="warning" outputSummary="OJ 暂不可用" />
    );
    expect(screen.getByText('降级')).toBeDefined();
    expect(container.firstChild.className).toContain('amber');
  });
});
