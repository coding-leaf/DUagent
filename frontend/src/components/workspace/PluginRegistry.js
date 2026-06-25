import QuizCard from './plugins/QuizCard';
import MermaidViewer from './plugins/MermaidViewer';
import MarkdownViewer from './plugins/MarkdownViewer';

export const PluginRegistry = {
  QuizCard,
  Mermaid: MermaidViewer,
  Markdown: MarkdownViewer
};
