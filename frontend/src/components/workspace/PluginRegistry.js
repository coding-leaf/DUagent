import QuizCard from './plugins/QuizCard';
import MermaidViewer from './plugins/MermaidViewer';
import MarkdownViewer from './plugins/MarkdownViewer';
import StudyPlanCard from './plugins/StudyPlanCard';
import WeakPointsCard from './plugins/WeakPointsCard';
import PathRecommendationCard from './plugins/PathRecommendationCard';

export const PluginRegistry = {
  QuizCard,
  Mermaid: MermaidViewer,
  Markdown: MarkdownViewer,
  StudyPlanCard,
  WeakPointsCard,
  PathRecommendationCard,
  StudyPlan: StudyPlanCard,
  WeakPoints: WeakPointsCard,
  PathRecommendation: PathRecommendationCard
};
