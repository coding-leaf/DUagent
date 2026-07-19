import QuizCard from './plugins/QuizCard';
import MermaidViewer from './plugins/MermaidViewer';
import MarkdownViewer from './plugins/MarkdownViewer';
import StudyPlanCard from './plugins/StudyPlanCard';
import WeakPointsCard from './plugins/WeakPointsCard';
import PathRecommendationCard from './plugins/PathRecommendationCard';
import CodeSandboxCard from './plugins/codeSandbox/CodeSandboxCard';
import PersonalizedResourceCard from './plugins/PersonalizedResourceCard';

export const PluginRegistry = {
  QuizCard,
  Mermaid: MermaidViewer,
  Markdown: MarkdownViewer,
  StudyPlanCard,
  WeakPointsCard,
  PathRecommendationCard,
  CodeSandboxCard,
  PersonalizedResourceCard
};
