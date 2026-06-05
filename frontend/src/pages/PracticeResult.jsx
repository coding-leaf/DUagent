import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { quizService } from '../api/services/quiz';
import { useCourse } from '../context/CourseContext';

export default function PracticeResult() {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeCourseId } = useCourse();
  const [resultData, setResultData] = useState(location.state?.result || null);
  const [loading, setLoading] = useState(!location.state?.result);

  useEffect(() => {
    if (!resultData && activeCourseId) {
      const fetchResult = async () => {
        try {
          const res = await quizService.getResult(activeCourseId);
          if (res.code === 200) {
            setResultData({
              score: res.data.latest_quiz.score,
              time_spent: res.data.latest_quiz.time_spent,
              total_count: 10,
              correct_count: Math.round((res.data.latest_quiz.score / 100) * 10),
              per_question_results: []
            });
          }
        } catch (error) {
          console.error("Failed to fetch result", error);
        } finally {
          setLoading(false);
        }
      };
      fetchResult();
    }
  }, [resultData, activeCourseId]);

  if (loading) {
    return (
      <div className="bg-surface min-h-screen flex items-center justify-center">
        <span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
      </div>
    );
  }

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const accuracy = resultData ? Math.round((resultData.correct_count / (resultData.total_count || 1)) * 100) : 0;


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
              <p className="font-body-md text-secondary">第4章：树形结构 - 平衡二叉树专项练习</p>
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
                    <span className="material-symbols-outlined">timer</span>
                  </div>
                  <div>
                    <span className="block font-label-sm text-label-sm text-secondary">练习耗时</span>
                    <span className="font-h3 text-h3 text-on-surface">{resultData ? formatTime(resultData.time_spent) : '0:00'}</span>
                  </div>
                </div>
                {/* Comparison Chart Placeholder */}
                <div className="col-span-2 bg-surface-container-lowest border-2 border-primary-container/20 p-md rounded-2xl relative overflow-hidden h-full flex items-center shadow-sm">
                  <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                    <span className="material-symbols-outlined text-[80px]">psychology</span>
                  </div>
                  <div className="flex gap-md w-full">
                    <div className="flex-shrink-0 h-12 w-12 rounded-xl bg-primary-container flex items-center justify-center text-white shadow-lg">
                      <span className="material-symbols-outlined">smart_toy</span>
                    </div>
                    <div className="flex-1">
                      <h4 className="font-body-lg font-bold text-on-surface mb-1">AI 智能教练建议</h4>
                      <p className="font-body-md text-on-surface-variant leading-relaxed text-sm">
                        {accuracy >= 80 ? (
                          <>总体表现优异！你在<span className="text-primary font-bold">基础知识点</span>上非常熟练。继续保持！</>
                        ) : (
                          <>表现一般，部分知识点仍需加强。建议针对错题进行强化训练。</>
                        )}
                      </p>
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
                        <span className="material-symbols-outlined text-[14px]">{q.is_correct ? 'bolt' : 'timer'}</span> 
                        正确答案是 {q.correct_answer}
                      </span>
                      <span className={`font-label-sm text-[11px] font-bold ${q.is_correct ? 'text-green-600' : 'text-error'}`}>
                        {q.is_correct ? '正确' : '错误'}
                      </span>
                    </div>
                  </div>
                  <span className="material-symbols-outlined text-secondary opacity-0 group-hover:opacity-100 transition-opacity">chevron_right</span>
                </div>
              ))}
              {(!resultData?.per_question_results || resultData.per_question_results.length === 0) && (
                <div className="text-center py-4 text-slate-400">暂无详细解析</div>
              )}
            </div>
          </div>

          {/* Modal Footer (Actions) */}
          <div className="px-xl py-lg bg-surface-container-low border-t border-surface-container flex gap-md justify-center">
            <button 
              onClick={() => navigate('/dashboard')}
              className="flex-1 max-w-[200px] h-12 rounded-xl border-2 border-primary-container text-primary font-bold hover:bg-primary-container/5 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span className="material-symbols-outlined">home</span>
              返回主页
            </button>
            <button 
              onClick={() => navigate('/quiz')}
              className="flex-1 max-w-[200px] h-12 rounded-xl bg-primary-container text-white font-bold shadow-lg shadow-primary-container/20 hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              下一组练习
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          </div>
        </div>
      </div>

      {/* Decorative Elements */}
      <div className="fixed top-20 right-10 z-10 w-48 h-48 pointer-events-none opacity-20">
        <div className="w-full h-full rounded-full border-2 border-primary-container animate-pulse flex items-center justify-center">
          <div className="w-4/5 h-4/5 rounded-full border border-dashed border-primary-container flex items-center justify-center">
            <span className="material-symbols-outlined text-primary-container text-4xl">account_tree</span>
          </div>
        </div>
      </div>
    </div>
  );
}
