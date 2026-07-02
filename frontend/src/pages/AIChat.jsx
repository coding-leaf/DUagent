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

      <div className="flex-1 flex overflow-hidden pt-16 relative">
        <SidebarHistory 
          leftCollapsed={leftCollapsed}
          leftDrawerOpen={leftDrawerOpen}
          onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
          onCloseDrawer={() => setLeftDrawerOpen(false)}
          onNewChat={handleNewChat}
        />

        <AgentWorkspace />

        <div className="absolute top-0 right-0 h-full p-4 pointer-events-none flex justify-end w-full lg:w-[480px] 2xl:w-[540px] z-10">
          <div className="pointer-events-auto w-full h-full">
            <ChatArea 
              key={activeSession || 'empty'}
              activeCourseName={activeCourseName}
              onOpenLeftDrawer={handleOpenLeftDrawer}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
