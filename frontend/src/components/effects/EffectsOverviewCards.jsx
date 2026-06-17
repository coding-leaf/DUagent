export default function EffectsOverviewCards({ overview, generatedAt }) {
  const formatDate = (value) => {
    if (!value) return '尚未生成';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '尚未生成';
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const cards = [
    ['KG 节点总数', overview.total],
    ['已练习节点', overview.practiced],
    ['待练习节点', overview.pending],
    ['未测评/默认通过', overview.defaultPass],
    ['最近评估时间', formatDate(generatedAt)],
  ];

  return (
    <section className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map(([label, value]) => (
        <div key={label} className="bg-white/80 backdrop-blur-md rounded-xl p-4 shadow-sm border border-gray-100 min-h-24">
          <div className="text-xs text-slate-400 mb-2">{label}</div>
          <div className="text-2xl font-bold text-slate-800 break-words">{value}</div>
        </div>
      ))}
    </section>
  );
}
