import { Link, useLocation } from 'react-router-dom';

import Navbar from '../components/Navbar';
import Icon from '../components/Icon';
import AgentTeamProgress from '../components/personalized/AgentTeamProgress';
import { useCourse } from '../context/CourseContext';
import usePersonalizedResourceGeneration from '../hooks/usePersonalizedResourceGeneration';

const RESOURCE_OPTIONS = [
  ['personal_lesson', '专业课程讲解'],
  ['diagram', '知识点思维导图'],
  ['practice', '不同类型练习题'],
  ['reading', '拓展阅读材料'],
  ['validated_code_problem', '代码类实操案例'],
];

export default function PersonalizedResourceGenerate() {
  const { activeCourseId } = useCourse();
  const location = useLocation();
  const generation = usePersonalizedResourceGeneration(activeCourseId, {
    goal: location.state?.goal,
    resourcePreferences: location.state?.resourcePreferences,
    sourceType: location.state?.sourceType,
  });

  return (
    <div className="min-h-screen bg-surface">
      <Navbar />
      <main className="mx-auto max-w-[896px] px-6 pt-24 pb-12">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-h2 text-h2 text-on-surface">智能生成个性化资源</h1>
            <p className="mt-2 text-secondary">描述学习目标，团队会完成生成、验证、独立审核与发布。</p>
          </div>
          <Link to="/personalized-resources" className="text-sm text-cyan-700 hover:underline">返回资源中心</Link>
        </div>

        <section className="rounded-2xl border border-outline-variant bg-white p-6 shadow-sm">
          <label htmlFor="resource-goal" className="block text-sm font-semibold text-slate-800">学习目标</label>
          <textarea
            id="resource-goal"
            aria-label="学习目标"
            value={generation.goal}
            onChange={(event) => generation.setGoal(event.target.value)}
            rows={5}
            placeholder="例如：我总是混淆数组与指针，请生成讲义、关系图和循序渐进的练习。"
            className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm outline-none focus:border-cyan-400"
          />

          <fieldset className="mt-5">
            <legend className="text-sm font-semibold text-slate-800">希望生成的资源（可多选）</legend>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {RESOURCE_OPTIONS.map(([value, label]) => (
                <label key={value} className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 p-3 hover:bg-cyan-50">
                  <input
                    type="checkbox"
                    aria-label={label}
                    checked={generation.preferences.includes(value)}
                    onChange={() => generation.togglePreference(value)}
                  />
                  <span className="text-sm text-slate-700">{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <button
            type="button"
            disabled={!generation.canSubmit || generation.status === 'submitting'}
            onClick={generation.submit}
            className="mt-6 flex items-center gap-2 rounded-xl bg-cyan-600 px-5 py-2.5 font-semibold text-white disabled:opacity-50"
          >
            <Icon name="groups" className="material-symbols-outlined" />
            启动多智能体生成
          </button>
          {generation.error && <p className="mt-3 text-sm text-error">提交失败，请稍后重试。</p>}
        </section>

        <div className="mt-6">
          <AgentTeamProgress status={generation.status} />
        </div>
      </main>
    </div>
  );
}
