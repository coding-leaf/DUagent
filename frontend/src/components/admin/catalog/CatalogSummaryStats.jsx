export default function CatalogSummaryStats({ summary }) {
  return (
    <section className="mb-5 grid grid-cols-2 gap-3">
      {[
        ['资料数', summary.material_count],
        ['知识切片', summary.chunk_count],
        ['待入库', summary.pending_material_count],
        ['失败资料', summary.failed_material_count]
      ].map(([label, value]) => (
        <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
          <div className="text-xs font-bold text-slate-500">{label}</div>
          <div className="mt-1 text-2xl font-bold text-slate-900">{value ?? 0}</div>
        </div>
      ))}
    </section>
  );
}
