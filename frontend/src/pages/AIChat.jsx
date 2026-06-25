import { useState } from 'react';
import { useCourse } from '../context/CourseContext';
import { useChat } from '../context/ChatContext';
import Navbar from '../components/Navbar';
import SidebarHistory from '../components/chat/SidebarHistory';
import AgentWorkspace from '../components/workspace/AgentWorkspace';
import ChatArea from '../components/chat/ChatArea';

export default function AIChat() {
  const { activeCourseId, courses } = useCourse();
  const { resetConversation, activeSession } = useChat();
  
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);

  const activeCourse = courses?.find(c => c.id === activeCourseId);
  const activeCourseName = activeCourse?.name || activeCourse?.title || '未选择课程';

  const handleNewChat = () => {
    resetConversation();
    setLeftDrawerOpen(false);
  };

  const handleOpenLeftDrawer = () => {
    setLeftDrawerOpen(true);
  };

  return (
    <div className="font-body-md text-slate-800 bg-slate-50 h-screen flex flex-col overflow-hidden">
      <Navbar />

      <div className="flex-1 flex overflow-hidden pt-16">
        <SidebarHistory 
          leftCollapsed={leftCollapsed}
          leftDrawerOpen={leftDrawerOpen}
          onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
          onCloseDrawer={() => setLeftDrawerOpen(false)}
          onNewChat={handleNewChat}
        />

        <AgentWorkspace />

        <ChatArea 
          key={activeSession || 'empty'}
          activeCourseName={activeCourseName}
          onOpenLeftDrawer={handleOpenLeftDrawer}
        />
      </div>
    </div>
  );
}
