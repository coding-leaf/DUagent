import { useNavigate, useLocation } from 'react-router-dom';
import { useCourse } from '../context/CourseContext';
import Icon from '../components/Icon';
import { usePracticeResult, LOADING_TEXTS } from '../hooks/usePracticeResult';

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s < 10 ? '0' : ''}${s}`;
};

export default function PracticeResult() {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeCourseId } = useCourse();
  
  const {
    resultData,
    diagnosisData,
    loading,
    generating,
    generateError,
    currentTextIndex,
    accuracy,
    contextKp,
    contextNodeId,
    handleGenerateWrongAnswerQuiz,
    handleRetry
  } = usePracticeResult({
    courseId: activeCourseId,
    initialResultData: location.state?.result,
    quizContext: location.state?.quizContext,
    navigate
  });

  if (loading) {
    return (
      <div className="bg-slate-50 min-h-screen flex items-center justify-center p-4">
        <div className="max-w-[448px] w-full bg-white border border-gray-100 rounded-3xl shadow-xl p-8 flex flex-col items-center text-center">
          <div className="relative flex items-center justify-center h-24 w-24 mb-6">
            {/* Outer spinning progress ring */}
            <div className="absolute inset-0 border-4 border-indigo-100 border-t-indigo-500 rounded-full animate-spin"></div>
            {/* Inner pulsing AI robot icon */}
            <Icon name="smart_toy" className="text-indigo-500 text-4xl animate-pulse"/>
          </div>
          <h3 className="text-2xl font-bold text-gray-800 mb-2 whitespace-nowrap">智能教练评估中</h3>
          <p className="text-sm font-medium text-gray-500 min-h-[24px]">
            {LOADING_TEXTS[currentTextIndex]}
          </p>
        </div>
      </div>
    );
  }






  return (
    <div className="bg-surface text-on-surface min-h-screen">
      {/* Blurred Background Mockup */}
      <div className="fixed inset-0 z-0 overflow-hidden opacity-40 select-none pointer-events-none">
        <div className="max-w-[1280px] mx-auto p-md grid grid-cols-12 gap-gutter h-full">
          <div className="col-span-3 border-r border-outline-variant py-md flex flex-col gap-sm">
            <div className="h-8 w-3/4 bg-surface-container-high rounded"></div>
            <div className="h-4 w-1/2 bg-surface-container rounded"></div>
            <div className="mt-lg h-12 bg-surface-container-highest rounded-lg"></div>
            <div className="h-12 bg-surface-container-highest rounded-lg"></div>
          </div>
          <div className="col-span-9 py-md">
            <div className="h-10 w-1/3 bg-surface-container-high rounded mb-md"></div>
            <div className="aspect-video w-full bg-white border border-outline-variant rounded-xl shadow-sm mb-md flex items-center justify-center">
              <div className="w-2/3 h-2/3 border-2 border-dashed border-primary-container/30 rounded-full"></div>
            </div>
            <div className="grid grid-cols-2 gap-md">
              <div className="h-32 bg-white rounded-xl border border-outline-variant"></div>
              <div className="h-32 bg-white rounded-xl border border-outline-variant"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Results Modal Overlay */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-md backdrop-blur-overlay">
        <div className="w-full max-w-[960px] bg-white rounded-[24px] shadow-[0px_8px_40px_rgba(0,0,0,0.08)] overflow-hidden flex flex-col max-h-[921px]">
          {/* Modal Header */}
          <div className="px-xl pt-lg pb-md flex justify-between items-end border-b border-surface-container">
            <div>
              <h2 className="font-h2 text-h2 text-on-surface mb-xs">训练完成</h2>
              <p className="font-body-md text-secondary">{contextKp ? `知识点：${contextKp}` : '综合练习'}</p>
            </div>
            <div className="text-right">
              <span className="font-label-sm text-label-sm text-primary uppercase tracking-widest bg-primary-container/10 px-3 py-1 rounded-full">Practice Report</span>
            </div>
          </div>

          {/* Modal Content Scroll Area */}
          <div className="flex-1 overflow-y-auto px-xl py-md custom-scrollbar">
            {/* Performance Overview Grid */}
            <div className="grid grid-cols-12 gap-md mb-lg items-stretch">
              {/* Accuracy Score */}
              <div className="col-span-4 bg-surface-container-low p-md rounded-xl flex flex-col items-center justify-center text-center">
                <span className="font-label-sm text-label-sm text-secondary mb-base">正确率</span>
                <div className="relative flex items-center justify-center h-24 w-24">
                  <svg className="absolute inset-0 h-24 w-24 transform -rotate-90">
                    <circle className="text-surface-container-highest" cx="48" cy="48" fill="transparent" r="40" stroke="currentColor" strokeWidth="8"></circle>
                    <circle className="text-primary-container" cx="48" cy="48" fill="transparent" r="40" stroke="currentColor" strokeDasharray="251.2" strokeDashoffset={251.2 - (251.2 * accuracy) / 100} strokeWidth="8"></circle>
                  </svg>
                  <span className="text-h3 font-h3 text-on-surface">{accuracy}%</span>
                </div>
              </div>
              {/* Time & Rank */}
              <div className="col-span-8 grid grid-cols-2 gap-md">
                <div className="bg-white border border-outline-variant p-md rounded-xl flex items-center gap-md">
                  <div className="h-12 w-12 bg-primary-container/10 rounded-full flex items-center justify-center text-primary-container">
                    <Icon name="timer" className="material-symbols-outlined"/>
                  </div>
                  <div>
                    <span className="block font-label-sm text-label-sm text-secondary">练习耗时</span>
                    <span className="font-h3 text-h3 text-on-surface">{resultData ? formatTime(resultData.time_spent) : '0:00'}</span>
                  </div>
                </div>
                {/* Comparison Chart Placeholder */}
                <div className="col-span-2 bg-surface-container-lowest border-2 border-primary-container/20 p-md rounded-2xl relative overflow-hidden h-full flex items-center shadow-sm">
                  <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                    <Icon name="psychology" className="material-symbols-outlined text-[80px]"/>
                  </div>
                  <div className="flex gap-md w-full">
                    <div className="flex-shrink-0 h-12 w-12 rounded-xl bg-primary-container flex items-center justify-center text-white shadow-lg">
                      <Icon name="smart_toy" className="material-symbols-outlined"/>
                    </div>
                    <div className="flex-1 overflow-y-auto max-h-[120px] custom-scrollbar pr-2">
                      <h4 className="font-body-lg font-bold text-on-surface mb-1">AI 智能教练建议</h4>
                      <div className="font-body-md text-on-surface-variant leading-relaxed text-sm space-y-1">
                        {diagnosisData ? (
                          <>
                            <p className="text-primary-container font-medium">{diagnosisData.summary}</p>
                            {diagnosisData.suggestions && diagnosisData.suggestions.length > 0 && (
                              <ul className="list-disc list-inside pl-1 text-on-surface">
                                {diagnosisData.suggestions.map((sug, idx) => (
                                  <li key={idx} className="break-words whitespace-normal">{sug}</li>
                                ))}
                              </ul>
                            )}
                          </>
                        ) : (
                          <p>
                            {accuracy >= 80 ? (
                              <>总体表现优异！你在<span className="text-primary font-bold">基础知识点</span>上非常熟练。继续保持！</>
                            ) : (
                              <>表现一般，部分知识点仍需加强。建议针对错题进行强化训练。</>
                            )}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Detailed Analysis List */}
            <div className="space-y-sm">
              <h4 className="font-label-sm text-label-sm text-secondary uppercase mb-base">详细解析回顾</h4>
              {resultData?.per_question_results?.map((q, idx) => (
                <div key={q.question_id} className={`group flex items-center gap-md p-md bg-white border rounded-xl transition-all cursor-pointer ${q.is_correct ? 'border-outline-variant hover:border-primary-container' : 'border-error/20 hover:border-error'}`}>
                  <div className={`flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center font-bold ${q.is_correct ? 'bg-green-50 text-green-600' : 'bg-error-container text-error'}`}>
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h5 className="font-body-md font-medium text-on-surface truncate">题号：{q.question_id} 的解析回顾</h5>
                    <div className="flex gap-sm mt-1">
                      <span className="font-label-sm text-[11px] text-secondary flex items-center gap-1">
                        <Icon name={q.is_correct ? 'bolt' : 'timer'} className="material-symbols-outlined text-[14px]"/> 
                        正确答案是 {q.correct_answer}
                      </span>
                      <span className={`font-label-sm text-[11px] font-bold ${q.is_correct ? 'text-green-600' : 'text-error'}`}>
                        {q.is_correct ? '正确' : '错误'}
                      </span>
                    </div>
                  </div>
                  <Icon name="chevron_right" className="material-symbols-outlined text-secondary opacity-0 group-hover:opacity-100 transition-opacity"/>
                </div>
              ))}
              {(!resultData?.per_question_results || resultData.per_question_results.length === 0) && (
                <div className="text-center py-4 text-slate-400">暂无详细解析</div>
              )}
            </div>
          </div>

          {/* Modal Footer (Actions) */}
          <div className="px-xl py-lg bg-surface-container-low border-t border-surface-container flex flex-col gap-md">
            {accuracy < 60 && resultData && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                <div className="flex items-start gap-3 mb-3">
                  <Icon name="warning" className="material-symbols-outlined text-amber-500 flex-shrink-0 mt-0.5"/>
                  <div>
                    <p className="text-body-md font-medium text-amber-800">
                      本次正确率较低（{accuracy}%）{contextKp ? `· 「${contextKp}」` : ''}
                    </p>
                    <p className="text-label-sm text-amber-600 mt-0.5">选择下一步：</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  {(contextKp || contextNodeId) && (
                    <button
                      onClick={handleRetry}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border-2 border-amber-400 text-amber-700 rounded-xl text-label-sm font-bold hover:bg-amber-100 active:scale-95 transition-all"
                    >
                      <Icon name="replay" className="material-symbols-outlined text-[16px]"/>
                      再练一遍
                    </button>
                  )}
                  <button
                    onClick={handleGenerateWrongAnswerQuiz}
                    disabled={generating}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-amber-500 text-white rounded-xl text-label-sm font-bold hover:bg-amber-600 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {generating
                      ? <Icon name="progress_activity" className="material-symbols-outlined text-[14px] animate-spin"/>
                      : <Icon name="auto_awesome" className="material-symbols-outlined text-[14px]"/>
                    }
                    {generating ? '生成中...' : '生成新一批'}
                  </button>
                </div>
                {generateError && <p className="text-error text-label-sm mt-2">{generateError}</p>}
              </div>
            )}
            <div className="flex gap-md justify-center">
              <button
                onClick={() => navigate('/dashboard')}
                className="flex-1 max-w-[200px] h-12 rounded-xl border-2 border-primary-container text-primary font-bold hover:bg-primary-container/5 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <Icon name="home" className="material-symbols-outlined"/>
                返回主页
              </button>
              <button
                onClick={() => navigate('/quiz')}
                className="flex-1 max-w-[200px] h-12 rounded-xl bg-primary-container text-white font-bold shadow-lg shadow-primary-container/20 hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                下一组练习
                <Icon name="arrow_forward" className="material-symbols-outlined"/>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Decorative Elements */}
      <div className="fixed top-20 right-10 z-10 w-48 h-48 pointer-events-none opacity-20">
        <div className="w-full h-full rounded-full border-2 border-primary-container animate-pulse flex items-center justify-center">
          <div className="w-4/5 h-4/5 rounded-full border border-dashed border-primary-container flex items-center justify-center">
            <Icon name="account_tree" className="material-symbols-outlined text-primary-container text-4xl"/>
          </div>
        </div>
      </div>
    </div>
  );
}
