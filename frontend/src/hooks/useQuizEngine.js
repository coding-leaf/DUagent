import { useState, useEffect, useRef, useCallback } from 'react';
import { quizService } from '../api/services/quiz';
import { learningActivityService } from '../api/services/learningActivity';
import { profileService } from '../api/services/profile';
import { useCourse } from '../context/CourseContext';
import { toast } from 'sonner';

const answerUpdaters = {
  multi_choice: (prev, qId, nextAnswer) => {
    const existing = Array.isArray(prev[qId]) ? prev[qId] : [];
    return {
      ...prev,
      [qId]: existing.includes(nextAnswer)
        ? existing.filter((item) => item !== nextAnswer)
        : [...existing, nextAnswer]
    };
  },
  multiple_choice: (prev, qId, nextAnswer) => {
    const existing = Array.isArray(prev[qId]) ? prev[qId] : [];
    return {
      ...prev,
      [qId]: existing.includes(nextAnswer)
        ? existing.filter((item) => item !== nextAnswer)
        : [...existing, nextAnswer]
    };
  },
  single_choice: (prev, qId, nextAnswer) => ({ ...prev, [qId]: nextAnswer }),
  short_answer: (prev, qId, nextAnswer) => ({ ...prev, [qId]: nextAnswer }),
  coding: (prev, qId, nextAnswer) => ({ ...prev, [qId]: nextAnswer }),
  default: (prev, qId, nextAnswer) => ({ ...prev, [qId]: nextAnswer }),
};

export function useQuizEngine({
  nodeId,
  sourceParam,
  knowledgePointParam,
  questionIdsParam,
  onNavigate
}) {
  const { activeCourseId, courses } = useCourse();
  
  const [quizData, setQuizData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  
  const quizStartRef = useRef(null);
  const practiceStartTrackedRef = useRef(null);

  useEffect(() => {
    const fetchQuestions = async () => {
      if (!activeCourseId) return;
      try {
        setLoading(true);
        setError(null);
        setCurrentQuestionIndex(0);
        setAnswers({});
        const extraParams = {};
        if (sourceParam) extraParams.source = sourceParam;
        if (knowledgePointParam) extraParams.knowledge_point = knowledgePointParam;
        if (questionIdsParam) extraParams.question_ids = questionIdsParam;
        
        const res = await quizService.getQuestions(activeCourseId, nodeId || undefined, extraParams);
        if (res.code === 200) {
          setQuizData(res.data);
          quizStartRef.current = Date.now();
        } else {
          throw new Error(res.message || "Failed to load questions");
        }
      } catch (err) {
        console.error("Failed to load questions", err);
        setError(err.message || "Failed to load questions");
        toast.error("加载题目失败，请稍后重试");
      } finally {
        setLoading(false);
      }
    };
    fetchQuestions();
  }, [activeCourseId, nodeId, sourceParam, knowledgePointParam, questionIdsParam]);

  useEffect(() => {
    const trackKp = knowledgePointParam || quizData?.questions?.[0]?.knowledge_point || null;
    if (!activeCourseId || (!nodeId && !trackKp) || !quizData?.quiz_id) return;
    if (practiceStartTrackedRef.current === quizData.quiz_id) return;
    practiceStartTrackedRef.current = quizData.quiz_id;
    const firstQuestion = quizData.questions?.[0];
    learningActivityService.trackActivity({
      course_id: activeCourseId,
      activity_type: 'node_practice_start',
      node_id: nodeId || null,
      node_name: firstQuestion?.knowledge_point || trackKp || null,
      quiz_id: quizData.quiz_id,
      metadata: { source: 'quiz' }
    });
  }, [activeCourseId, nodeId, quizData, knowledgePointParam]);

  const handleAnswerChange = useCallback((nextAnswer) => {
    if (!quizData) return;
    const currentQ = quizData.questions[currentQuestionIndex];
    const normalizedType = String(currentQ?.type || '').toLowerCase();
    
    setAnswers((prev) => {
      const updater = answerUpdaters[normalizedType] || answerUpdaters.default;
      return updater(prev, currentQ.id, nextAnswer);
    });
  }, [quizData, currentQuestionIndex]);

  const handleNextOrSubmit = useCallback(async () => {
    if (!quizData) return;
    
    if (currentQuestionIndex < quizData.questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
      return;
    }

    const elapsedSeconds = Math.max(
      0,
      Math.floor((Date.now() - (quizStartRef.current || Date.now())) / 1000)
    );
    try {
      setSubmitting(true);
      const submitData = {
        quiz_id: quizData.quiz_id,
        time_spent: elapsedSeconds,
        answers: Object.entries(answers).map(([qId, ans]) => ({
          question_id: qId,
          answer: ans
        }))
      };
      const res = await quizService.submitQuiz(submitData);
      if (res.code === 200) {
        if (activeCourseId) {
          profileService.refreshProfile(activeCourseId).catch(() => {});
        }
        onNavigate('/quiz/result', {
          state: {
            result: res.data,
            quizContext: {
              node_id: nodeId || null,
              knowledge_point: knowledgePointParam || quizData.questions?.[0]?.knowledge_point || null,
              source: sourceParam || null,
            },
          },
        });
      } else {
        throw new Error(res.message || "Failed to submit quiz");
      }
    } catch (err) {
      console.error("Failed to submit quiz", err);
      toast.error("提交失败，请重试");
    } finally {
      const trackKp = knowledgePointParam || quizData.questions?.[0]?.knowledge_point || null;
      if (activeCourseId && (nodeId || trackKp)) {
        learningActivityService.trackActivity({
          course_id: activeCourseId,
          activity_type: 'node_practice_submit',
          node_id: nodeId || null,
          node_name: trackKp,
          quiz_id: quizData.quiz_id,
          duration_seconds: elapsedSeconds,
          metadata: { source: sourceParam || 'quiz' }
        });
      }
      setSubmitting(false);
    }
  }, [quizData, currentQuestionIndex, answers, activeCourseId, nodeId, knowledgePointParam, sourceParam, onNavigate]);

  const handlePrev = useCallback(() => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
    } else {
      onNavigate(-1);
    }
  }, [currentQuestionIndex, onNavigate]);

  return {
    quizData,
    loading,
    error,
    currentQuestionIndex,
    answers,
    submitting,
    handleAnswerChange,
    handleNextOrSubmit,
    handlePrev,
    activeCourseId,
    courses,
    nodeId,
    sourceParam,
    knowledgePointParam,
    questionIdsParam
  };
}
