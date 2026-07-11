import Icon from '../Icon';
export default function ChatEmptyState({ onCardClick, courseName = '当前课程' }) {
  const suggestCards = [
    {
      icon: 'lightbulb',
      title: '解释关键概念',
      prompt: `帮我解释${courseName}里的一个核心概念，并给出例子。`,
      color: 'amber'
    },
    {
      icon: 'code_blocks',
      title: '分析代码或思路',
      prompt: `帮我分析一段和${courseName}相关的代码或解题思路。`,
      color: 'emerald'
    },
    {
      icon: 'menu_book',
      title: '推荐学习方向',
      prompt: `请根据${courseName}推荐我接下来应该学习的方向。`,
      color: 'indigo'
    },
    {
      icon: 'calendar_month',
      title: '规划复习安排',
      prompt: `我想复习${courseName}的薄弱点，请帮我规划一周学习安排。`,
      color: 'rose'
    }
  ];

  const getColorClasses = (color) => {
    const classes = {
      amber: 'bg-amber-50 text-amber-600 group-hover:bg-amber-100',
      emerald: 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100',
      indigo: 'bg-indigo-50 text-indigo-600 group-hover:bg-indigo-100',
      rose: 'bg-rose-50 text-rose-600 group-hover:bg-rose-100'
    };
    return classes[color];
  };

  return (
    <div className="h-full flex flex-col items-center justify-center py-10 px-4">
      <div className="w-16 h-16 bg-gradient-to-tr from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-200/50 mb-6 relative">
        <Icon name="smart_toy" className="material-symbols-outlined text-[32px] text-white"/>
        <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-400 rounded-full border-2 border-white"></div>
      </div>
      
      <h2 className="text-2xl font-bold text-slate-800 mb-2">你好，我是你的智能助教</h2>
      <p className="text-slate-500 mb-10 text-center max-w-[448px] leading-relaxed">
        我可以帮你解答疑惑、分析代码、规划学习路线，或者基于资料进行知识拓展。
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-[672px]">
        {suggestCards.map((card, idx) => (
          <div 
            key={idx}
            onClick={() => onCardClick(card.prompt)}
            className="group bg-white border border-slate-200 rounded-2xl p-4 cursor-pointer hover:border-cyan-300 hover:shadow-md transition-all duration-300 flex items-start gap-4"
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors ${getColorClasses(card.color)}`}>
              <Icon name={card.icon} className="material-symbols-outlined text-[20px]"/>
            </div>
            <div>
              <h3 className="font-semibold text-slate-700 text-[15px] mb-1 group-hover:text-cyan-700 transition-colors">{card.title}</h3>
              <p className="text-slate-500 text-[13px] leading-relaxed line-clamp-2">{card.prompt}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
