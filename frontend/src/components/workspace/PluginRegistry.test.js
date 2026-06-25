import { expect, test } from 'vitest';
import { PluginRegistry } from './PluginRegistry';

test('PluginRegistry resolves standard component types correctly', () => {
  expect(PluginRegistry.QuizCard).toBeDefined();
  expect(PluginRegistry.Mermaid).toBeDefined();
  expect(PluginRegistry.Markdown).toBeDefined();
});
