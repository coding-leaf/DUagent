const suggestions = [
  {
    icon: 'school',
    title: '解释知识点',
    description: '例如：帮我解释 C 语言指针和数组的关系',
    prompt: '帮我解释 C 语言指针和数组的关系，请给出简单易懂的示例。'
  },
  {
    icon: 'code',
    title: '分析代码',
    description: '例如：帮我分析这段代码为什么会段错误',
    prompt: '我有一段代码运行时出现了段错误（Segmentation Fault），你能帮我分析一下可能的原因并教我如何调试吗？'
  },
  {
    icon: 'library_books',
    title: '推荐资源',
    description: '例如：给我推荐适合复习指针的学习资料',
    prompt: '我想重点复习 C 语言的指针部分，请给我推荐一些高质量的学习资料、视频课程或练习题。'
  },
  {
    icon: 'route',
    title: '规划复习',
    description: '例如：我想一周内补齐动态内存分配',
    prompt: '我的动态内存分配学得不太好，如果我想在一周内补齐这部分的知识，你能帮我制定一个详细的复习规划吗？'
  }
];

export default function ChatEmptyState({ onCardClick }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center animate-fade-in max-w-3xl mx-auto w-full">
      <div className="w-16 h-16 bg-gradient-to-tr from-cyan-500 to-sky-400 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-500/20 mb-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-white/20 backdrop-blur-sm"></div>
        <span className="material-symbols-outlined text-[32px] text-white relative z-10" style={{ fontVariationSettings: '"FILL" 1' }}>
          robot_2
        </span>
      </div>
      
      <h2 className="text-2xl font-bold text-slate-800 mb-2">有什么我可以帮您的？</h2>
      <p className="text-slate-500 mb-10 max-w-md">您可以直接在下方输入问题，或者从以下常见场景中选择一个开始。</p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
        {suggestions.map((item, idx) => (
          <button
            key={idx}
            onClick={() => onCardClick?.(item.prompt)}
            className="flex items-start gap-4 p-4 rounded-2xl bg-white border border-slate-200 shadow-sm hover:shadow-md hover:border-cyan-200 hover:-translate-y-0.5 transition-all duration-300 text-left group"
          >
            <div className="w-10 h-10 rounded-xl bg-slate-50 group-hover:bg-cyan-50 flex items-center justify-center flex-shrink-0 transition-colors">
              <span className="material-symbols-outlined text-slate-400 group-hover:text-cyan-500 transition-colors">
                {item.icon}
              </span>
            </div>
            <div>
              <h3 className="font-semibold text-slate-700 group-hover:text-cyan-700 mb-1 transition-colors">{item.title}</h3>
              <p className="text-xs text-slate-500 leading-relaxed">{item.description}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
