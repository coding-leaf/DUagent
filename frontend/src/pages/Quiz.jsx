import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { quizService } from '../api/services/quiz';

export default function Quiz() {
  const navigate = useNavigate();
  const [quizData, setQuizData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        setLoading(true);
        const res = await quizService.getQuestions('default_course', 'tree');
        if (res.code === 200) {
          setQuizData(res.data);
        }
      } catch (error) {
        console.error("Failed to load questions", error);
      } finally {
        setLoading(false);
      }
    };
    fetchQuestions();
  }, []);

  const handleOptionSelect = (optionKey) => {
    if (!quizData) return;
    const currentQ = quizData.questions[currentQuestionIndex];
    setAnswers(prev => ({
      ...prev,
      [currentQ.id]: optionKey
    }));
  };

  const handleNextOrSubmit = async () => {
    if (!quizData) return;
    
    // 如果不是最后一题，进入下一题
    if (currentQuestionIndex < quizData.questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
      return;
    }

    // 最后一题，提交答案
    try {
      setSubmitting(true);
      const submitData = {
        quiz_id: quizData.quiz_id,
        time_spent: 120, // dummy time
        answers: Object.entries(answers).map(([qId, ans]) => ({
          question_id: qId,
          answer: ans
        }))
      };
      const res = await quizService.submitQuiz(submitData);
      if (res.code === 200) {
        navigate('/quiz/result', { state: { result: res.data } });
      }
    } catch (error) {
      console.error("Failed to submit quiz", error);
    } finally {
      setSubmitting(false);
    }
  };

  const handlePrev = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
    } else {
      navigate(-1);
    }
  };

  if (loading) {
    return (
      <div className="bg-surface min-h-screen flex items-center justify-center">
        <span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
      </div>
    );
  }

  if (!quizData || !quizData.questions || quizData.questions.length === 0) {
    return (
      <div className="bg-surface min-h-screen flex items-center justify-center flex-col gap-4">
        <p className="text-slate-500">无法加载题目，请稍后再试。</p>
        <button onClick={() => navigate(-1)} className="text-primary hover:underline">返回上一页</button>
      </div>
    );
  }

  const currentQuestion = quizData.questions[currentQuestionIndex];
  const totalQuestions = quizData.questions.length;
  const progressPercent = Math.round(((currentQuestionIndex + 1) / totalQuestions) * 100);


  return (
    <div className="bg-surface text-on-surface font-body-md min-h-screen">
      {/* Top Navigation Bar */}
      <header className="fixed top-0 z-50 w-full bg-white/80 backdrop-blur-md border-b border-slate-100 shadow-[0px_4px_20px_rgba(0,0,0,0.04)]">
        <div className="relative flex justify-between items-center h-16 px-6 max-w-[1280px] mx-auto">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate(-1)} 
              className="p-2 hover:bg-slate-100 rounded-full transition-colors cursor-pointer flex items-center justify-center -ml-2 text-slate-600 hover:text-slate-900"
              title="返回上一页"
            >
              <span className="material-symbols-outlined">arrow_back</span>
            </button>
            <span className="text-xl font-bold tracking-tighter text-slate-900">数据结构智慧训练</span>
          </div>
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">timer</span>
            <span className="font-body-md text-primary font-bold tracking-tight">18:45</span>
          </div>
          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-slate-50 rounded-full transition-colors active:scale-95 duration-200 cursor-pointer">
              <span className="material-symbols-outlined text-slate-600">analytics</span>
            </button>
            <button className="p-2 hover:bg-slate-50 rounded-full transition-colors active:scale-95 duration-200 cursor-pointer">
              <span className="material-symbols-outlined text-slate-600">notifications</span>
            </button>
            <div className="w-8 h-8 rounded-full overflow-hidden border border-slate-200">
              <img alt="用户头像" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBD7zzVzJP4sOCCImNhQnVh0f5VXBKYUUdqITWBaQkw7NykTFWpBCRb35x5OdjOfAeHA8pxnY1dbeHj7om4AmK_nGXsoIN-1mbwE3hCNq7xFNt4SuldmZvdW3PqPIvYRwW_EBGaXqZId-3waaJh8IQcMRBeypeQMRJI5hJFBhbeybYWhNhoWkUKSfTBuQqCIzu6dKwDMXS9LUFS_FZN0utek2XOAcc_3gZ3uXN6djZJ4T2_TfvwsvZ-1jgokz1Htpu6VTO_yqFDEOvS" />
            </div>
          </div>
        </div>
      </header>

      {/* Side Navigation Bar */}
      <aside className="h-screen w-64 border-r fixed left-0 top-0 bg-slate-50 border-slate-200 z-40 hidden xl:flex flex-col pt-20 pb-6 px-4 gap-2">
        <div className="px-4 py-4 mb-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white">
              <span className="material-symbols-outlined">smart_toy</span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">第4章：树形结构</h3>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1">
          <div className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:bg-slate-100 hover:pl-6 transition-all duration-300 cursor-pointer rounded-lg">
            <span className="material-symbols-outlined text-sm">dashboard</span>
            <span className="font-label-sm text-xs font-medium">练习概览</span>
          </div>
          <div className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:bg-slate-100 hover:pl-6 transition-all duration-300 cursor-pointer rounded-lg">
            <span className="material-symbols-outlined text-sm">account_tree</span>
            <span className="font-label-sm text-xs font-medium">数据结构基础</span>
          </div>
          <div className="flex items-center gap-3 px-4 py-3 bg-white text-primary shadow-sm rounded-lg border-l-4 border-primary font-bold">
            <span className="material-symbols-outlined text-sm">lan</span>
            <span className="font-label-sm text-xs font-medium">树与二叉树</span>
          </div>
          <div className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:bg-slate-100 hover:pl-6 transition-all duration-300 cursor-pointer rounded-lg">
            <span className="material-symbols-outlined text-sm">hub</span>
            <span className="font-label-sm text-xs font-medium">图论算法</span>
          </div>
          <div className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:bg-slate-100 hover:pl-6 transition-all duration-300 cursor-pointer rounded-lg">
            <span className="material-symbols-outlined text-sm">smart_toy</span>
            <span className="font-label-sm text-xs font-medium">智能体助手</span>
          </div>
        </nav>
        <div className="mt-auto px-4">
          <button 
            onClick={handleNextOrSubmit}
            disabled={submitting}
            className="w-full py-3 bg-primary text-white font-bold rounded-xl active:scale-95 transition-all shadow-lg shadow-primary/20 cursor-pointer disabled:opacity-50"
          >
            {submitting ? '提交中...' : '提交本次练习'}
          </button>
        </div>
      </aside>

      {/* Main Content Canvas */}
      <main className="xl:ml-64 pt-20 min-h-screen px-6 pb-24">
        <div className="max-w-[800px] mx-auto mt-8">
          {/* Progress Header */}
          <div className="bg-white rounded-2xl p-6 mb-8 border border-slate-200 shadow-[0px_4px_20px_rgba(0,0,0,0.04)]">
            <div className="flex justify-between items-end mb-4">
              <div>
                <span className="text-primary font-bold text-h3 font-h3">{currentQuestionIndex + 1}</span>
                <span className="text-slate-400 font-body-md"> / {totalQuestions} 题</span>
              </div>
              <div className="text-right">
                <span className="text-slate-500 font-label-sm text-[11px] block mb-1">完成进度 {progressPercent}%</span>
              </div>
            </div>
            <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${progressPercent}%` }}></div>
            </div>
          </div>

          {/* Question Area */}
          <section className="bg-white rounded-2xl p-8 border border-slate-200 shadow-[0px_4px_20px_rgba(0,0,0,0.04)]">
            <div className="flex items-start gap-4 mb-6">
              <span className="bg-primary-container text-on-primary-container px-3 py-1 rounded-lg font-bold text-sm shrink-0">
                {currentQuestion.type === 'single_choice' ? '单选题' : '未知题型'}
              </span>
              <h2 className="font-h3 text-h3 text-on-surface flex-1">
                {currentQuestion.content}
              </h2>
            </div>

            {/* Technical Visualization Placeholder (Static mockup for now) */}
            <div className="w-full h-48 bg-slate-50 rounded-xl mb-8 flex items-center justify-center border border-dashed border-slate-200 relative overflow-hidden group">
              <div className="absolute inset-0 opacity-20 pointer-events-none">
                <div className="w-full h-full" style={{ backgroundImage: 'radial-gradient(#00d1ff 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>
              </div>
              <div className="flex flex-col items-center gap-3 relative z-10">
                <span className="material-symbols-outlined text-primary/40 text-4xl">account_tree</span>
                <p className="text-slate-400 font-label-sm">节点索引关系示意图区域</p>
              </div>
            </div>

            {/* Options List */}
            <div className="space-y-4">
              {currentQuestion.options && currentQuestion.options.map(option => {
                const isSelected = answers[currentQuestion.id] === option.key;
                return (
                  <label 
                    key={option.key} 
                    className={`group flex items-center p-5 rounded-xl border-2 transition-all cursor-pointer ${
                      isSelected ? 'border-primary bg-primary/5' : 'border-slate-200 hover:border-primary hover:bg-primary/5'
                    }`}
                  >
                    <input 
                      className="w-5 h-5 text-primary border-slate-300 focus:ring-primary" 
                      name={`question-${currentQuestion.id}`} 
                      type="radio" 
                      checked={isSelected}
                      onChange={() => handleOptionSelect(option.key)}
                    />
                    <span className={`ml-4 font-body-md transition-colors ${
                      isSelected ? 'text-primary font-bold' : 'text-on-surface group-hover:text-primary'
                    }`}>
                      {option.key}. {option.text}
                    </span>
                  </label>
                );
              })}
            </div>
          </section>

          {/* Bottom Action Controls */}
          <div className="fixed bottom-0 left-0 xl:left-64 right-0 bg-white/90 backdrop-blur-lg border-t border-slate-100 p-4 z-40">
            <div className="max-w-[800px] mx-auto flex justify-between items-center gap-4">
              <button 
                onClick={handlePrev}
                className="flex items-center gap-2 px-6 py-3 text-slate-600 font-bold hover:bg-slate-100 rounded-xl transition-all cursor-pointer"
              >
                <span className="material-symbols-outlined">arrow_back</span>
                {currentQuestionIndex === 0 ? '退出练习' : '上一题'}
              </button>
              <div className="flex gap-4">
                <button 
                  onClick={handleNextOrSubmit}
                  disabled={submitting}
                  className="flex items-center gap-2 px-8 py-3 bg-primary text-white font-bold hover:opacity-90 rounded-xl transition-all shadow-lg shadow-primary/20 active:scale-95 cursor-pointer disabled:opacity-50"
                >
                  {submitting ? '提交中...' : (currentQuestionIndex < totalQuestions - 1 ? '下一题' : '提交本题')}
                  {!submitting && <span className="material-symbols-outlined">chevron_right</span>}
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Contextual FAB for Agent Help (Minimalist) */}
      <button className="fixed bottom-24 right-8 w-14 h-14 bg-white border border-slate-200 rounded-full shadow-xl flex items-center justify-center text-primary hover:scale-110 transition-transform active:scale-95 group z-50 cursor-pointer">
        <span className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}>support_agent</span>
        <div className="absolute right-16 bg-on-surface text-white text-[10px] py-1 px-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
          获取AI解题思路
        </div>
      </button>
    </div>
  );
}
