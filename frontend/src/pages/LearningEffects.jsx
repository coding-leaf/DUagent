import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import Icon from '../components/Icon';
import { useLearningEffects } from '../hooks/useLearningEffects';
import EffectsOverviewCards from '../components/effects/EffectsOverviewCards';
import EffectsSummaryCard from '../components/effects/EffectsSummaryCard';
import MasteryDistributionCard from '../components/effects/MasteryDistributionCard';
import KnowledgeProgressTable from '../components/effects/KnowledgeProgressTable';

export default function LearningEffects() {
  const { activeCourseId } = useCourse();

  const {
    effectsData,
    effectsLoading,
    effectsError,
    isPolling: refreshInProgress,
    refreshFailed,
    refreshFailureMessage,
    overview,
    masteryDistribution,
    nodeRows,
    handleRefresh,
  } = useLearningEffects(activeCourseId);

  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen">
      <Navbar />

      <main className="pt-24 pb-12 px-6 max-w-[1280px] mx-auto min-h-screen">
        <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="font-h1 text-h1 text-on-surface text-4xl font-bold mb-2">学习效果展示</h1>
            <p className="text-body-md text-outline mt-2 text-slate-500">基于课程知识图谱、练习记录和评估快照的节点掌握情况</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleRefresh}
              disabled={!activeCourseId || refreshInProgress}
              className="flex items-center px-4 py-2 bg-primary-container text-on-primary-container rounded-xl font-label-sm text-label-sm font-bold shadow-sm hover:brightness-110 active:scale-95 transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Icon name="refresh" className="material-symbols-outlined mr-2"/>
              {refreshInProgress ? '评估中' : '重新评估'}
            </button>
          </div>
        </div>

        {!activeCourseId && (
          <div className="bg-white border border-gray-100 rounded-xl p-8 text-center text-slate-500">
            请先加入或选择课程
          </div>
        )}

        {activeCourseId && (
          <div className="space-y-6">
            {effectsError && (
              <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl px-4 py-3 text-sm">
                {effectsError}
              </div>
            )}

            {refreshFailed && (
              <div className="bg-amber-50 border border-amber-100 text-amber-700 rounded-xl px-4 py-3 text-sm">
                {refreshFailureMessage}
              </div>
            )}

            <EffectsOverviewCards
              overview={overview}
              generatedAt={effectsData?.generated_at}
            />

            <section className="grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-8">
                <EffectsSummaryCard
                  summaryText={effectsData?.summary_text}
                  loading={effectsLoading}
                />
              </div>

              <div className="col-span-12 lg:col-span-4">
                <MasteryDistributionCard
                  masteryDistribution={masteryDistribution}
                  totalNodes={overview.total}
                />
              </div>
            </section>

            <KnowledgeProgressTable
              nodeRows={nodeRows}
              activeCourseId={activeCourseId}
            />
          </div>
        )}
      </main>
    </div>
  );
}
