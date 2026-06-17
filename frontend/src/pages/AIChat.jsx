import { useState } from 'react';
import { useCourse } from '../context/CourseContext';
import { useChat } from '../context/ChatContext';
import Navbar from '../components/Navbar';
import SidebarHistory from '../components/chat/SidebarHistory';
import SidebarResources from '../components/chat/SidebarResources';
import ChatArea from '../components/chat/ChatArea';

export default function AIChat() {
  const { activeCourseId, courses } = useCourse();
  const { resetConversation, activeSession } = useChat();
  
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);

  const activeCourse = courses?.find(c => c.id === activeCourseId);
  const activeCourseName = activeCourse?.name || activeCourse?.title || '未选择课程';

  const handleNewChat = () => {
    resetConversation();
    setLeftDrawerOpen(false);
  };

  const handleOpenLeftDrawer = () => {
    setLeftDrawerOpen(true);
    setRightDrawerOpen(false);
  };

  const handleOpenRightDrawer = () => {
    setRightDrawerOpen(true);
    setLeftDrawerOpen(false);
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

        <ChatArea 
          key={activeSession || 'empty'}
          activeCourseName={activeCourseName}
          onOpenLeftDrawer={handleOpenLeftDrawer}
          onOpenRightDrawer={handleOpenRightDrawer}
        />

        <SidebarResources 
          activeCourseName={activeCourseName}
          rightCollapsed={rightCollapsed}
          rightDrawerOpen={rightDrawerOpen}
          onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
          onCloseDrawer={() => setRightDrawerOpen(false)}
        />
      </div>
    </div>
  );
}
