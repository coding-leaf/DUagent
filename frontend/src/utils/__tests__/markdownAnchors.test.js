import { describe, expect, it } from 'vitest';
import { markdownHeadingId } from '../markdownAnchors';

describe('markdownHeadingId', () => {
  it('creates a stable anchor ID for mixed Chinese and numeric headings', () => {
    expect(markdownHeadingId(['第 1 章：', '线性代数'])).toBe('第-1-章线性代数');
  });

  it('handles incomplete streaming headings safely', () => {
    expect(markdownHeadingId(undefined)).toBe('');
  });
});
