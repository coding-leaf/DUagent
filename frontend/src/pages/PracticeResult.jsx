import { useNavigate, useLocation } from 'react-router-dom';
import { useCourse } from '../context/CourseContext';
import Icon from '../components/Icon';
import { usePracticeResult, LOADING_TEXTS } from '../hooks/usePracticeResult';
import ResultLoadingState from '../components/quiz/ResultLoadingState';
import ResultScoreBoard from '../components/quiz/ResultScoreBoard';
import QuestionReviewList from '../components/quiz/QuestionReviewList';

export default function PracticeResult() {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeCourseId } = useCourse();
  
  const {
    resultData,
    diagnosisData,
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

  if (!resultData) {
    return <ResultLoadingState currentTextIndex={currentTextIndex} LOADING_TEXTS={LOADING_TEXTS} />;
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
            <ResultScoreBoard accuracy={accuracy} resultData={resultData} diagnosisData={diagnosisData} />
            <QuestionReviewList perQuestionResults={resultData?.per_question_results} />
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
