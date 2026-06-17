import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuizEngine } from '../hooks/useQuizEngine';
import QuestionRenderer from '../components/quiz/QuestionRenderer';
import { getQuestionTypeLabel } from '../components/quiz/questionTypeMeta';
import Icon from '../components/Icon';
import QuizHeader from '../components/quiz/QuizHeader';
import QuizProgressCard from '../components/quiz/QuizProgressCard';
import QuizSidebar from '../components/quiz/QuizSidebar';
import QuizFooter from '../components/quiz/QuizFooter';

export default function Quiz() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  const nodeId = searchParams.get('node_id');
  const sourceParam = searchParams.get('source');
  const knowledgePointParam = searchParams.get('knowledge_point');
  const questionIdsParam = searchParams.get('question_ids');

  const {
    quizData,
    loading,
    currentQuestionIndex,
    answers,
    submitting,
    handleAnswerChange,
    handleNextOrSubmit,
    handlePrev,
    activeCourseId,
    courses
  } = useQuizEngine({
    nodeId,
    sourceParam,
    knowledgePointParam,
    questionIdsParam,
    onNavigate: navigate
  });

  if (loading) {
    return (
      <div className="bg-surface min-h-screen flex items-center justify-center">
        <Icon name="progress_activity" className="material-symbols-outlined animate-spin text-4xl text-primary"/>
      </div>
    );
  }

  if (!quizData || !quizData.questions || quizData.questions.length === 0) {
    return (
      <div data-testid="quiz-empty" className="bg-surface min-h-screen flex items-center justify-center flex-col gap-4">
        <p className="text-slate-500">无法加载题目，请稍后再试。</p>
        <button onClick={() => navigate(-1)} className="text-primary hover:underline">返回上一页</button>
      </div>
    );
  }

  const currentQuestion = quizData.questions[currentQuestionIndex];
  const totalQuestions = quizData.questions.length;

  const activeCourse = courses.find((course) => course.id === activeCourseId);
  const courseName = activeCourse?.name || '课程练习';
  const currentChapter = currentQuestion.chapter || quizData.chapter || '当前章节';
  const currentKnowledgePoint = currentQuestion.knowledge_point || currentQuestion.knowledgePoint || '综合练习';
  const sourceLabel = {
    baseline: '保底题库',
    common: '公共题库',
    personalized: '个性化题'
  }[currentQuestion.source] || '题库';
  const difficultyLabel = {
    easy: '简单',
    medium: '中等',
    hard: '困难'
  }[currentQuestion.difficulty] || currentQuestion.difficulty || '未标注';


  return (
    <div className="bg-surface text-on-surface font-body-md min-h-screen">
      <QuizSidebar 
        currentChapter={currentChapter}
        sourceLabel={sourceLabel}
        difficulty={difficultyLabel}
        knowledgePoint={currentKnowledgePoint}
        questionTypeLabel={getQuestionTypeLabel(currentQuestion.type)}
      />

      <QuizHeader 
        courseName={courseName}
        currentKnowledgePoint={currentKnowledgePoint}
        onExit={() => navigate(-1)}
      />

      {/* Main Content Canvas */}
      <main className="xl:ml-64 pt-20 min-h-screen px-6 pb-24">
        <div className="max-w-[800px] mx-auto mt-8">
          <QuizProgressCard 
            currentQuestionIndex={currentQuestionIndex}
            totalQuestions={totalQuestions}
          />

          {/* Question Area */}
          <section data-testid="quiz-question" className="bg-white rounded-2xl p-8 border border-slate-200 shadow-[0px_4px_20px_rgba(0,0,0,0.04)]">
            <div className="flex items-start gap-4 mb-6">
              <span className="bg-primary-container text-on-primary-container px-3 py-1 rounded-lg font-bold text-sm shrink-0">
                {getQuestionTypeLabel(currentQuestion.type)}
              </span>
              <h2 className="font-h3 text-h3 text-on-surface flex-1">
                {currentQuestion.content}
              </h2>
            </div>

            <div className="w-full bg-slate-50 rounded-xl mb-8 border border-slate-200 relative overflow-hidden">
              <div className="absolute inset-0 opacity-20 pointer-events-none">
                <div className="w-full h-full" style={{ backgroundImage: 'radial-gradient(#00d1ff 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>
              </div>
              <div className="relative z-10 grid grid-cols-1 sm:grid-cols-3 gap-3 p-5">
                <div className="sm:col-span-3 flex items-center gap-2 text-slate-500 text-xs font-bold uppercase tracking-wide">
                  <Icon name="info" className="material-symbols-outlined text-primary text-base"/>
                  当前题目上下文
                </div>
                <div className="rounded-lg bg-white/80 border border-white px-4 py-3">
                  <span className="block text-[11px] text-slate-400 mb-1">章节</span>
                  <span className="block text-sm font-bold text-slate-800 truncate">{currentChapter}</span>
                </div>
                <div className="rounded-lg bg-white/80 border border-white px-4 py-3">
                  <span className="block text-[11px] text-slate-400 mb-1">知识点</span>
                  <span className="block text-sm font-bold text-slate-800 truncate">{currentKnowledgePoint}</span>
                </div>
                <div className="rounded-lg bg-white/80 border border-white px-4 py-3">
                  <span className="block text-[11px] text-slate-400 mb-1">来源 / 难度</span>
                  <span className="block text-sm font-bold text-slate-800 truncate">{sourceLabel} · {difficultyLabel}</span>
                </div>
              </div>
            </div>

            <QuestionRenderer
              question={currentQuestion}
              value={answers[currentQuestion.id]}
              onChange={handleAnswerChange}
            />
          </section>

          <QuizFooter 
            isFirst={currentQuestionIndex === 0}
            isLast={currentQuestionIndex >= totalQuestions - 1}
            onPrevious={handlePrev}
            onNextOrSubmit={handleNextOrSubmit}
            submitting={submitting}
            hasAnsweredCurrent={!!answers[currentQuestion.id]}
          />
        </div>
      </main>

      {/* Contextual FAB for Agent Help (Minimalist) */}
      <button className="fixed bottom-24 right-8 w-14 h-14 bg-white border border-slate-200 rounded-full shadow-xl flex items-center justify-center text-primary hover:scale-110 transition-transform active:scale-95 group z-50 cursor-pointer">
        <Icon name="support_agent" className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}/>
        <div className="absolute right-16 bg-on-surface text-white text-[10px] py-1 px-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
          获取AI解题思路
        </div>
      </button>
    </div>
  );
}
