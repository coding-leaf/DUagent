export default function UnsupportedQuestionCard({ question }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-6 text-sm text-slate-600">
      当前前端暂未开放 `{question?.type || 'unknown'}` 题型的作答界面。
    </div>
  );
}
