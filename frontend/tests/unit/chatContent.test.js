import { test } from 'node:test';
import assert from 'node:assert';
import { normalizeMessage } from '../../src/utils/chatContent.js';

test('normalizeMessage extracts diagrams and content correctly', () => {
  const input = { role: 'assistant', content: '{"content":"hello", "diagram":"graph TD"}' };
  const result = normalizeMessage(input);
  assert.strictEqual(result.content, 'hello');
  assert.deepStrictEqual(result.diagrams, ['graph TD']);
});
