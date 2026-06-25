import { useChat } from '../../context/ChatContext';
import { PluginRegistry } from './PluginRegistry';
import Icon from '../Icon';

export default function AgentWorkspace() {
  const { workspaceArtifacts } = useChat();

  return (
    <div className="flex-grow flex flex-col bg-slate-50 border-r border-slate-200 overflow-y-auto custom-scrollbar p-6">
      <div className="flex items-center gap-2 mb-6 flex-shrink-0">
        <Icon name="design_services" className="material-symbols-outlined text-slate-600 text-[20px]" />
        <h2 className="text-base font-semibold text-slate-800">Agent 工作区</h2>
      </div>

      <div className="flex-1 space-y-6">
        {workspaceArtifacts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
            <Icon name="dashboard_customize" className="material-symbols-outlined text-[48px] mb-3 text-slate-300" />
            <p className="text-sm">暂无生成产物，请在右侧与 AI 互动生成学习路径、卡片或图表</p>
          </div>
        ) : (
          workspaceArtifacts.map((artifact) => {
            const Component = PluginRegistry[artifact.type];
            if (!Component) {
              return (
                <div key={artifact.id} className="p-4 bg-red-50 text-red-800 border border-red-200 rounded-xl text-sm">
                  未知插件类型: {artifact.type}
                </div>
              );
            }
            return (
              <div key={artifact.id} className="transition-all duration-300 transform scale-98 animate-fadeIn">
                <Component {...artifact.props} />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
