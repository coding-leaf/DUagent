# Quiz Result Loading Screen Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase the quiz results loading screen wait time to 5 seconds and display a dynamic rotating loading text that matches the light theme style.

**Architecture:** Use a React hook to periodically update state text indices, rendering a centered card component with a spinner, AI pulsing icon, and rotating status message.

**Tech Stack:** React 18, Tailwind CSS, Material Symbols Outlined.

---

### Task 1: Update PracticeResult.jsx Logic and UI

**Files:**
- Modify: `src/pages/PracticeResult.jsx`

- [ ] **Step 1: Modify loading state logic and styling in PracticeResult.jsx**

Edit [PracticeResult.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/PracticeResult.jsx) to add `LOADING_TEXTS` array, `currentTextIndex` state, and an interval updating the text. Update the `setTimeout` fetching duration to `5000`ms. Render a clean styled card with rotating copywriting texts.

Find the following imports and state declarations:
```javascript
import { useState, useEffect } from 'react';
```
And:
```javascript
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);
```

Add the state for the text rotation:
```javascript
  const [currentTextIndex, setCurrentTextIndex] = useState(0);

  const LOADING_TEXTS = [
    "正在接收本次作答数据...",
    "正在分析知识点掌握情况...",
    "正在评估薄弱环节与能力表现...",
    "正在生成个性化学习建议..."
  ];
```

In the `useEffect` that handles fetching, update it to set up the interval to rotate the texts and increase the timeout duration:
```javascript
  useEffect(() => {
    let isMounted = true;
    let textInterval = null;

    if (activeCourseId) {
      // Set up dynamic rotating texts
      textInterval = setInterval(() => {
        if (isMounted) {
          setCurrentTextIndex((prev) => {
            if (prev < LOADING_TEXTS.length - 1) {
              return prev + 1;
            }
            return prev; // Hold at the last step
          });
        }
      }, 1250);

      const fetchDiagnosis = async () => {
        try {
          const res = await quizService.getResult(activeCourseId);
          if (res.code === 200 && isMounted) {
            setDiagnosisData(res.data.diagnosis);
            if (!resultData && res.data.latest_quiz) {
              setResultData({
                score: res.data.latest_quiz.score,
                time_spent: res.data.latest_quiz.time_spent,
                total_count: 10,
                correct_count: Math.round((res.data.latest_quiz.score / 100) * 10),
                per_question_results: []
              });
            }
          }
        } catch (error) {
          console.error("Failed to fetch diagnosis result", error);
        } finally {
          if (isMounted) setLoading(false);
        }
      };
      
      // Delay fetching slightly to allow backend AI task to complete
      const timer = setTimeout(() => {
        fetchDiagnosis();
      }, 5000);

      return () => {
        isMounted = false;
        clearTimeout(timer);
        if (textInterval) clearInterval(textInterval);
      };
    } else {
      setTimeout(() => setLoading(false), 0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCourseId]); // 仅依赖 activeCourseId，挂载后获取一次
```

Update the loading JSX block:
```javascript
  if (loading) {
    return (
      <div className="bg-surface min-h-screen flex items-center justify-center p-md">
        <div className="flex flex-col items-center justify-center p-xl bg-white border border-outline-variant rounded-2xl shadow-[0px_4px_24px_rgba(0,0,0,0.04)] max-w-sm w-full text-center">
          <div className="relative mb-lg flex items-center justify-center h-16 w-16">
            {/* Outer spinning progress indicator */}
            <span className="material-symbols-outlined animate-spin text-5xl text-primary absolute">
              progress_activity
            </span>
            {/* Inner pulsing AI Coach icon */}
            <span className="material-symbols-outlined text-2xl text-primary absolute animate-pulse">
              smart_toy
            </span>
          </div>
          <h3 className="font-h3 text-h3 text-on-surface mb-sm">智能教练评估中</h3>
          <div className="h-12 flex items-center justify-center">
            <p className="font-body-md text-secondary transition-all duration-300 animate-pulse">
              {LOADING_TEXTS[currentTextIndex]}
            </p>
          </div>
        </div>
      </div>
    );
  }
```

- [ ] **Step 2: Verify code syntax by compiling/running linter and builder**

Run command:
`npm run lint && npm run build`
Expected: Passes with no syntax errors.

- [ ] **Step 3: Commit files**

Run command:
`git add src/pages/PracticeResult.jsx && git commit -m "feat: 优化答题后加载动画与动态文案，并延长等待时长至 5 秒"`
Expected: Clean commit.
