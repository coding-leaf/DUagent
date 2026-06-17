import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { quizService } from '../api/services/quiz';
import { learningActivityService } from '../api/services/learningActivity';
import { profileService } from '../api/services/profile';
import { useCourse } from '../context/CourseContext';

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

export function useQuizEngine() {
  const navigate = useNavigate();
  const { activeCourseId, courses } = useCourse();
  const [searchParams] = useSearchParams();
  
  const nodeId = searchParams.get('node_id');
  const sourceParam = searchParams.get('source');
  const knowledgePointParam = searchParams.get('knowledge_point');
  const questionIdsParam = searchParams.get('question_ids');
  
  const [quizData, setQuizData] = useState(null);
  const [loading, setLoading] = useState(true);
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
        }
      } catch (error) {
        console.error("Failed to load questions", error);
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCourseId, nodeId, quizData]);

  const handleAnswerChange = (nextAnswer) => {
    if (!quizData) return;
    const currentQ = quizData.questions[currentQuestionIndex];
    const normalizedType = String(currentQ?.type || '').toLowerCase();
    
    setAnswers((prev) => {
      const updater = answerUpdaters[normalizedType] || answerUpdaters.default;
      return updater(prev, currentQ.id, nextAnswer);
    });
  };

  const handleNextOrSubmit = async () => {
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
        navigate('/quiz/result', {
          state: {
            result: res.data,
            quizContext: {
              node_id: nodeId || null,
              knowledge_point: knowledgePointParam || quizData.questions?.[0]?.knowledge_point || null,
              source: sourceParam || null,
            },
          },
        });
      }
    } catch (error) {
      console.error("Failed to submit quiz", error);
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
  };

  const handlePrev = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
    } else {
      navigate(-1);
    }
  };

  return {
    quizData,
    loading,
    currentQuestionIndex,
    answers,
    submitting,
    handleAnswerChange,
    handleNextOrSubmit,
    handlePrev,
    navigate,
    activeCourseId,
    courses,
    nodeId,
    sourceParam,
    knowledgePointParam,
    questionIdsParam
  };
}
