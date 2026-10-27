import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ResourceDetail, { TYPE_LABELS, sanitizeResourceContent } from './ResourceDetail';
import { useResourceDetail } from '../hooks/useResourceDetail';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ state: { node: { id: 'node-1' } } }),
  useParams: () => ({ id: 'cdc46410bb074398' }),
}));

vi.mock('../context/CourseContext', () => ({
  useCourse: () => ({
    activeCourseId: 'course-101',
    loading: false,
  }),
}));

vi.mock('../hooks/useResourceDetail', () => ({
  useResourceDetail: vi.fn(),
}));

vi.mock('../hooks/useResourceStudyTracking', () => ({
  useResourceStudyTracking: vi.fn(),
}));

vi.mock('../components/Icon', () => ({
  default: ({ name, className }) => <span className={className} data-testid={`icon-${name}`}>{name}</span>,
}));

vi.mock('../components/common/MarkdownViewer', () => ({
  default: ({ content, className }) => (
    <div data-testid="markdown-viewer" className={className} dangerouslySetInnerHTML={{ __html: content }} />
  ),
}));

describe('sanitizeResourceContent', () => {
  it('returns empty string for empty or non-string input', () => {
    expect(sanitizeResourceContent('')).toBe('');
    expect(sanitizeResourceContent(null)).toBe('');
    expect(sanitizeResourceContent(undefined)).toBe('');
    expect(sanitizeResourceContent(123)).toBe('');
  });

  it('preserves standard markdown content that does not have slide structure', () => {
    const md = '# 核心概念与原理\n\n- 机制 A\n- 机制 B\n\n```python\nprint("hello")\n```';
    expect(sanitizeResourceContent(md, 'personal_lesson')).toBe(md);
  });

  it('cleans script tags, dead nav buttons, and unhides all slides in historical slide decks', () => {
    const legacyHtml = `
      <style>
        body { font-family: sans-serif; background: red; }
        .slide { display: none; }
        .slide.active { display: block; }
      </style>
      <div id="deck">
        <div class="slide active">
          <h2>易错点 1: 内存越界</h2>
          <p>详细讲解 1</p>
        </div>
        <div class="slide">
          <h2>易错点 2: 野指针</h2>
          <p>详细讲解 2</p>
        </div>
        <div class="slide">
          <h2>易错点 3: 内存泄漏</h2>
          <p>详细讲解 3</p>
        </div>
        <div id="nav">
          <button id="prev">上一页</button>
          <button id="next">下一页</button>
        </div>
      </div>
      <script>
        document.getElementById('prev').onclick = function() {};
      </script>
    `;

    const cleaned = sanitizeResourceContent(legacyHtml, 'personal_lesson');

    // 1. Script is removed
    expect(cleaned).not.toContain('<script');
    expect(cleaned).not.toContain('document.getElementById');

    // 2. Dead navigation and buttons are removed
    expect(cleaned).not.toContain('id="nav"');
    expect(cleaned).not.toContain('上一页');
    expect(cleaned).not.toContain('下一页');

    // 3. Body style is sanitized to avoid global pollution
    expect(cleaned).not.toMatch(/body\s*\{[^}]*\}/i);

    // 4. Slide display:none is replaced and forced to block
    expect(cleaned).toContain('.slide { display: block !important; margin-bottom: 2rem; }');

    // 5. All 3 sections are preserved
    expect(cleaned).toContain('易错点 1: 内存越界');
    expect(cleaned).toContain('易错点 2: 野指针');
    expect(cleaned).toContain('易错点 3: 内存泄漏');
  });

  it('handles edge cases: unclosed script, html/body styles, and link buttons in section.slide', () => {
    const rawWithEdgeCases = `
      <style>
        html, body { background: #000; color: #fff; }
      </style>
      <section class="slide">
        <h3>Section Slide Item</h3>
        <a href="#prev" class="btn">上一页</a>
        <a href="#next" class="btn">下一页</a>
      </section>
      <script>
        console.log("unclosed script cutoff at stream end...
    `;

    const cleaned = sanitizeResourceContent(rawWithEdgeCases, 'personal_lesson');

    expect(cleaned).not.toContain('<script');
    expect(cleaned).not.toContain('unclosed script');
    expect(cleaned).not.toContain('上一页');
    expect(cleaned).not.toContain('下一页');
    expect(cleaned).not.toMatch(/(?:html\s*,\s*)?body/i);
    expect(cleaned).toContain('Section Slide Item');
    expect(cleaned).toContain('.slide { display: block !important;');
  });
});

describe('ResourceDetail Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "专业课程讲解" badge for personal_lesson resource type', () => {
    expect(TYPE_LABELS.personal_lesson).toBe('专业课程讲解');

    useResourceDetail.mockReturnValue({
      loading: false,
      resource: {
        id: 'cdc46410bb074398',
        title: 'C语言指针易错点精讲',
        type: 'personal_lesson',
        description: '重点剖析三大常见陷阱',
        chapter: '第 5 章',
        knowledge_point: '指针',
        content: '# 结构化讲义\n\n内容展示',
        tags: ['lesson', 'kg_node:指针'],
      },
    });

    render(<ResourceDetail />);

    // Top badge recognizes personal_lesson
    expect(screen.getByText('专业课程讲解')).toBeInTheDocument();
    expect(screen.getByText('C语言指针易错点精讲')).toBeInTheDocument();
    expect(screen.getByText('章节: 第 5 章')).toBeInTheDocument();
    expect(screen.getByText('知识点: 指针')).toBeInTheDocument();
    expect(screen.getByText('知识节点: 指针')).toBeInTheDocument();
  });

  it('cleans and renders legacy slide deck cdc46410bb074398 with all slides visible and buttons removed', () => {
    const historicalSlideDeck = `
      <style>
        body { margin: 0; padding: 20px; }
        .slide { display: none; }
      </style>
      <div id="deck">
        <div class="slide">
          <h2>1. 指针越界访问</h2>
          <pre><code>int arr[5]; arr[5] = 10;</code></pre>
        </div>
        <div class="slide">
          <h2>2. 未初始化指针</h2>
          <pre><code>int *p; *p = 20;</code></pre>
        </div>
        <div class="slide">
          <h2>3. 返回局部变量地址</h2>
          <pre><code>int* func() { int a = 1; return &a; }</code></pre>
        </div>
        <div id="nav">
          <button id="prev">上一页</button>
          <button id="next">下一页</button>
        </div>
      </div>
      <script>
        console.log('slide script');
      </script>
    `;

    useResourceDetail.mockReturnValue({
      loading: false,
      resource: {
        id: 'cdc46410bb074398',
        title: '指针避坑指南',
        type: 'personal_lesson',
        content: historicalSlideDeck,
        tags: ['lesson'],
      },
    });

    render(<ResourceDetail />);

    expect(screen.getByText('专业课程讲解')).toBeInTheDocument();
    expect(screen.getByText('1. 指针越界访问')).toBeInTheDocument();
    expect(screen.getByText('2. 未初始化指针')).toBeInTheDocument();
    expect(screen.getByText('3. 返回局部变量地址')).toBeInTheDocument();

    // Dead buttons & script are not rendered
    expect(screen.queryByText('上一页')).toBeNull();
    expect(screen.queryByText('下一页')).toBeNull();
    const viewer = screen.getByTestId('markdown-viewer');
    expect(viewer.innerHTML).not.toContain('<script');
    expect(viewer.innerHTML).not.toContain('id="nav"');
  });

  it('renders loading state when fetching', () => {
    useResourceDetail.mockReturnValue({
      loading: true,
      resource: null,
    });

    render(<ResourceDetail />);
    expect(screen.getByText('加载资源详情中...')).toBeInTheDocument();
  });

  it('renders not found state when resource is missing', () => {
    useResourceDetail.mockReturnValue({
      loading: false,
      resource: null,
    });

    render(<ResourceDetail />);
    expect(screen.getByText('未找到该资源或获取失败')).toBeInTheDocument();
  });
});
