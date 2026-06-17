import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useCourse } from '../context/CourseContext';
import { useLearningPath } from '../hooks/useLearningPath';
import Navbar from '../components/Navbar';
import Icon from '../components/Icon';
import PathVisualizer from '../components/learning/PathVisualizer';
import NodeResourcePanel from '../components/learning/NodeResourcePanel';

export default function LearningPath() {
  const { activeCourseId } = useCourse();
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  
  const { 
    learningPath, pathLoading, 
    nodeResources, resourcesLoading 
  } = useLearningPath(activeCourseId, selectedNodeId, setSelectedNodeId);

  return (
    <div className="font-body-md bg-background min-h-screen text-on-background">
      <Navbar />

      <main className="pt-16 min-h-screen">
        <div className="max-w-[1280px] mx-auto p-gutter space-y-md">
          {/* Header Section */}
          <header className="flex flex-col md:flex-row md:items-end justify-between gap-md mb-sm">
            <div>
              <h1 className="font-h1 text-h1 text-on-background">学习路径规划</h1>
            </div>
          </header>

          <PathVisualizer 
            learningPath={learningPath} 
            loading={pathLoading} 
            selectedNodeId={selectedNodeId} 
            onSelectNode={setSelectedNodeId} 
          />

          <NodeResourcePanel 
            activeCourseId={activeCourseId} 
            selectedNodeId={selectedNodeId} 
            nodeResources={nodeResources} 
            resourcesLoading={resourcesLoading} 
          />
        </div>
      </main>

      {/* Contextual Floating Action Button */}
      <Link to="/ai-chat" className="fixed bottom-margin right-margin w-14 h-14 bg-cyan-500 text-white rounded-full shadow-2xl flex items-center justify-center hover:scale-110 active:scale-90 transition-all z-50">
        <Icon name="auto_awesome" className="material-symbols-outlined text-2xl"/>
      </Link>
    </div>
  );
}
