import { useState, useEffect, useCallback, useMemo } from 'react';
import { quizService } from '../api/services/quiz';
import { personalizedResourcesService } from '../api/services/personalizedResources';
import { learningService } from '../api/services/learning';
import { profileService } from '../api/services/profile';

export const LOADING_TEXTS = [
  "正在接收本次作答数据...",
  "正在分析知识点掌握情况...",
  "正在评估薄弱环节与能力表现...",
  "正在生成个性化学习建议..."
];

export function usePracticeResult({ courseId, initialResultData, quizContext, navigate }) {
  const [resultData, setResultData] = useState(initialResultData || null);
  const [diagnosisData, setDiagnosisData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);
  const [currentTextIndex, setCurrentTextIndex] = useState(0);

  const contextKp = quizContext?.knowledge_point || null;
  const contextSource = quizContext?.source || null;
  const contextNodeId = quizContext?.node_id || null;

  const accuracy = resultData ? Math.round((resultData.correct_count / (resultData.total_count || 1)) * 100) : 0;

  useEffect(() => {
    if (accuracy >= 60 && courseId && resultData) {
      learningService.refreshEvaluation(courseId).catch(() => {});
      profileService.refreshProfile(courseId).catch(() => {});
    }
  }, [accuracy, courseId, resultData]);

  useEffect(() => {
    let isMounted = true;
    let intervalTimer = null;
    let fetchTimer = null;

    if (courseId) {
      const fetchDiagnosis = async () => {
        try {
          const res = await quizService.getResult(courseId);
          if (res.code === 200 && isMounted) {
            setDiagnosisData(res.data.diagnosis);
            setResultData(prev => {
              if (!prev && res.data.latest_quiz) {
                return {
                  score: res.data.latest_quiz.score,
                  time_spent: res.data.latest_quiz.time_spent,
                  total_count: 10,
                  correct_count: Math.round((res.data.latest_quiz.score / 100) * 10),
                  per_question_results: []
                };
              }
              return prev;
            });
          }
        } catch (error) {
          console.error("Failed to fetch diagnosis result", error);
        } finally {
          if (isMounted) {
            setLoading(false);
            if (intervalTimer) clearInterval(intervalTimer);
          }
        }
      };

      intervalTimer = setInterval(() => {
        if (isMounted) {
          setCurrentTextIndex((prev) => {
            if (prev < LOADING_TEXTS.length - 1) {
              return prev + 1;
            }
            return prev;
          });
        }
      }, 1250);
      
      fetchTimer = setTimeout(() => {
        fetchDiagnosis();
      }, 5000);

      return () => {
        isMounted = false;
        if (intervalTimer) clearInterval(intervalTimer);
        clearTimeout(fetchTimer);
      };
    } else {
      fetchTimer = setTimeout(() => {
        if (isMounted) setLoading(false);
      }, 0);
      return () => {
        isMounted = false;
        clearTimeout(fetchTimer);
      };
    }
  }, [courseId]);

  const wrongQuestionIds = useMemo(() => {
    return resultData?.per_question_results
      ?.filter(q => !q.is_correct)
      .map(q => q.question_id)
      .filter(Boolean) || [];
  }, [resultData]);

  const handleGenerateWrongAnswerQuiz = useCallback(async () => {
    if (!courseId) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const payload = {
        course_id: courseId,
        generate_type: 'quiz',
        source_type: 'quiz_wrong_answer',
        count: 5,
      };
      if (wrongQuestionIds.length > 0) payload.wrong_question_ids = wrongQuestionIds;
      if (contextKp) payload.knowledge_point = contextKp;
      await personalizedResourcesService.generate(payload);
      navigate('/personalized-resources', { state: { newTaskId: 'triggered' } });
    } catch {
      setGenerateError('生成失败，请稍后重试');
      setGenerating(false);
    }
  }, [courseId, contextKp, navigate, wrongQuestionIds]);

  const handleRetry = useCallback(() => {
    const params = new URLSearchParams({ course_id: courseId });
    if (contextSource === 'personalized' && contextKp) {
      params.set('source', 'personalized');
      params.set('knowledge_point', contextKp);
    } else if (contextNodeId) {
      params.set('node_id', contextNodeId);
    }
    navigate(`/quiz?${params.toString()}`);
  }, [courseId, contextSource, contextKp, contextNodeId, navigate]);

  return {
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
  };
}
