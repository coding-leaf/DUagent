export default function EffectsOverviewCards({ overview }) {
  const cards = [
    ['KG 节点总数', overview.total, 'text-slate-800'],
    ['已掌握节点', overview.mastered, 'text-emerald-600'],
    ['薄弱节点', overview.weak, 'text-red-600'],
    ['学习中节点', overview.learning, 'text-cyan-600'],
    ['待练习节点', overview.pending, 'text-amber-600'],
    ['未开始/默认通过', overview.unstarted, 'text-slate-500'],
  ];

  return (
    <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {cards.map(([label, value, textColor]) => (
        <div key={label} className="bg-white/80 backdrop-blur-md rounded-xl p-4 shadow-sm border border-gray-100 min-h-24 flex flex-col justify-between">
          <div className="text-xs text-slate-400 font-semibold">{label}</div>
          <div className={`text-2xl font-bold break-words ${textColor}`}>{value}</div>
        </div>
      ))}
    </section>
  );
}
