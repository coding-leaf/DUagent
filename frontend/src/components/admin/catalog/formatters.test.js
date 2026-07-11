import { describe, expect, it } from 'vitest';

import { RESOURCE_TYPE_OPTIONS, formatResourceType } from './formatters';


describe('public resource type presentation', () => {
  it('offers only truthful generation types', () => {
    expect(RESOURCE_TYPE_OPTIONS).toEqual([
      { value: 'lesson', label: '标准讲义' },
      { value: 'diagram', label: '知识图解' },
      { value: 'example', label: '代码示例' },
    ]);
  });

  it('keeps labels for legacy stored resources', () => {
    expect(formatResourceType('lesson')).toBe('标准讲义');
    expect(formatResourceType('document')).toBe('旧版文档');
  });
});
