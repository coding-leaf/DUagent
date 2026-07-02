import { useChat } from '../../context/ChatContext';
import { PluginRegistry } from './PluginRegistry';
import Icon from '../Icon';
import WorkspaceTabs from './WorkspaceTabs';

export default function AgentWorkspace() {
  const { workspaceArtifacts, activeArtifactId, setActiveArtifactId } = useChat();

  const activeArtifact = workspaceArtifacts.find(a => a.id === activeArtifactId) || workspaceArtifacts[0];

  return (
    <div className="relative h-full flex-grow flex flex-col bg-slate-50 border-r border-slate-200 overflow-hidden">
      <div className="flex items-center gap-2 p-6 pb-2 flex-shrink-0">
        <Icon name="design_services" className="material-symbols-outlined text-slate-600 text-[20px]" />
        <h2 className="text-base font-semibold text-slate-800">Agent 画布</h2>
      </div>

      {workspaceArtifacts.length > 0 && (
        <div className="px-6 flex-shrink-0">
          <WorkspaceTabs 
            artifacts={workspaceArtifacts} 
            activeId={activeArtifact?.id} 
            onSelect={setActiveArtifactId} 
          />
        </div>
      )}

      <div className="flex-1 overflow-y-auto custom-scrollbar bg-white/50 backdrop-blur-sm m-4 mt-0 rounded-lg border shadow-sm p-6 pt-4">
        {workspaceArtifacts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
            <Icon name="dashboard_customize" className="material-symbols-outlined text-[48px] mb-3 text-slate-300" />
            <p className="text-sm">暂无生成产物，请在右侧与 AI 互动生成学习路径、卡片或图表</p>
          </div>
        ) : activeArtifact ? (
          (() => {
            const Component = PluginRegistry[activeArtifact.type];
            if (!Component) {
              return (
                <div key={activeArtifact.id} className="p-4 bg-red-50 text-red-800 border border-red-200 rounded-xl text-sm">
                  未知插件类型: {activeArtifact.type}
                </div>
              );
            }
            return (
              <div key={activeArtifact.id} className="transition-all duration-300 transform scale-98 animate-fadeIn h-full">
                <Component {...activeArtifact.props} />
              </div>
            );
          })()
        ) : null}
      </div>
    </div>
  );
}
