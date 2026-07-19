import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import AgentTeamProgress from './AgentTeamProgress';

describe('AgentTeamProgress', () => {
  it('shows leader, generator, validator and reviewer roles', () => {
    render(<AgentTeamProgress status="started" />);

    expect(screen.getByText('学习规划 Leader')).toBeInTheDocument();
    expect(screen.getByText('资源生成 Agent')).toBeInTheDocument();
    expect(screen.getByText('确定性验证工具')).toBeInTheDocument();
    expect(screen.getByText('独立审核 Agent')).toBeInTheDocument();
  });
});
