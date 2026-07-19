import { afterEach, describe, expect, it } from 'vitest';
import { getCachedSvg, mermaidCache, setCachedSvg } from '../mermaid';

describe('Mermaid SVG cache', () => {
  afterEach(() => {
    mermaidCache.clear();
  });

  it('returns the SVG stored for a Mermaid source', () => {
    setCachedSvg('graph TD; A-->B', '<svg />');

    expect(getCachedSvg('graph TD; A-->B')).toBe('<svg />');
  });
});
