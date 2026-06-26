import { expect, test } from 'vitest';
import { PluginRegistry } from './PluginRegistry';

test('PluginRegistry resolves standard component types correctly', () => {
  expect(PluginRegistry.QuizCard).toBeDefined();
  expect(PluginRegistry.Mermaid).toBeDefined();
  expect(PluginRegistry.Markdown).toBeDefined();
  expect(PluginRegistry.StudyPlanCard).toBeDefined();
  expect(PluginRegistry.WeakPointsCard).toBeDefined();
  expect(PluginRegistry.PathRecommendationCard).toBeDefined();
  expect(PluginRegistry.StudyPlan).toBeDefined();
  expect(PluginRegistry.WeakPoints).toBeDefined();
  expect(PluginRegistry.PathRecommendation).toBeDefined();
});
