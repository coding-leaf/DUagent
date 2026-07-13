const headingText = (children) => {
  if (!children) return '';
  if (Array.isArray(children)) return children.map(headingText).join('');
  if (typeof children === 'string' || typeof children === 'number') return String(children);

  const nested = children?.props?.children;
  if (nested === undefined || nested === children) return '';
  return headingText(nested);
};

export const markdownHeadingId = (children) => headingText(children)
  .trim()
  .toLowerCase()
  .replace(/[^\p{L}\p{N}\s-]/gu, '')
  .replace(/[\s-]+/g, '-');
