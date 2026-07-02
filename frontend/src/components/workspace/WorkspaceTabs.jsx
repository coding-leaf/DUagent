import Icon from '../Icon';

export default function WorkspaceTabs({ artifacts, activeId, onSelect }) {
  if (!artifacts || artifacts.length === 0) return null;
  return (
    <div className="flex gap-2 p-2 border-b border-slate-200 overflow-x-auto custom-scrollbar flex-shrink-0">
      {artifacts.map(art => (
        <button
          key={art.id}
          onClick={() => onSelect(art.id)}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
            activeId === art.id 
              ? 'bg-white text-cyan-600 border-t-2 border-cyan-500 shadow-sm' 
              : 'bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-700'
          }`}
        >
          <Icon name="insert_drive_file" className="text-[16px] inline-block mr-1 align-text-bottom" />
          {art.title || art.type}
        </button>
      ))}
    </div>
  );
}
