import { useState } from 'react';

import { personalizedResourcesService } from '../api/services/personalizedResources';

export default function usePersonalizedResourceGeneration(courseId, initial = {}) {
  const [goal, setGoal] = useState(initial.goal || '');
  const [preferences, setPreferences] = useState(initial.resourcePreferences || []);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const togglePreference = (type) => {
    setPreferences((current) => current.includes(type)
      ? current.filter((item) => item !== type)
      : [...current, type]);
  };

  const submit = async () => {
    setStatus('submitting');
    setError(null);
    try {
      const response = await personalizedResourcesService.generate({
        course_id: courseId,
        goal: goal.trim(),
        source_type: initial.sourceType || 'manual',
        resource_preferences: preferences,
      });
      setResult(response.data);
      setStatus('started');
      return response.data;
    } catch (submissionError) {
      setError(submissionError);
      setStatus('failed');
      return null;
    }
  };

  return {
    goal,
    setGoal,
    preferences,
    togglePreference,
    status,
    result,
    error,
    submit,
    canSubmit: Boolean(courseId && goal.trim() && preferences.length),
  };
}
