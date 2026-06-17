# Quiz Domain Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the `Quiz.jsx` and `PracticeResult.jsx` pages into thin containers by extracting logic into MVVM view-models (`useQuizEngine.js`, `usePracticeResult.js`) and UI into presentational components.

**Architecture:** MVVM + Container/Presentational components. State machines for logic flows (fetching, answering, submitting, evaluating). `answerUpdaters` dispatch table for scalable question types.

**Tech Stack:** React, Tailwind CSS, SWR (Optional here since we manage timer/state manually), React Router.

---

### Task 1: Extract `useQuizEngine` ViewModel

**Files:**
- Create: `src/hooks/useQuizEngine.js`

- [ ] **Step 1: Write the Hook implementation**
Create `src/hooks/useQuizEngine.js` moving all logic from `Quiz.jsx` (L27-152) including:
  - State: `quizData`, `loading`, `currentQuestionIndex`, `answers`, `submitting`.
  - Ref: `quizStartRef`, `practiceStartTrackedRef`.
  - Effect: `fetchQuestions` logic.
  - Effect: `node_practice_start` tracking logic.
  - Constants: `answerUpdaters` dispatch table for `single_choice`, `multi_choice`, `short_answer`, `coding`.
  - Function: `handleAnswerChange` utilizing the `answerUpdaters` table.
  - Function: `handleNextOrSubmit` which handles the submit API (`quizService.submitQuiz`), the tracking (`learningActivityService.trackActivity` for `node_practice_submit`), the profile refresh (`profileService.refreshProfile`), and navigation.
  - Ensure the hook returns all necessary state and functions.

- [ ] **Step 2: Commit**
```bash
git add src/hooks/useQuizEngine.js
git commit -m "feat(quiz): extract useQuizEngine hook"
```

---

### Task 2: Extract Quiz Presentational Components

**Files:**
- Create: `src/components/quiz/QuizHeader.jsx`
- Create: `src/components/quiz/QuizSidebar.jsx`
- Create: `src/components/quiz/QuizFooter.jsx`

- [ ] **Step 1: Create `QuizHeader.jsx`**
Extract the top navigation and progress bar UI from `Quiz.jsx`. Props needed: `currentQuestionIndex`, `totalQuestions`, `courseName`, `onExit`.

- [ ] **Step 2: Create `QuizSidebar.jsx`**
Extract the left-side metadata panel. Props needed: `questionTypeLabel`, `difficulty`, `knowledgePoint`.

- [ ] **Step 3: Create `QuizFooter.jsx`**
Extract the bottom navigation buttons. Props needed: `isFirst`, `isLast`, `onPrevious`, `onNextOrSubmit`, `submitting`, `hasAnsweredCurrent`.

- [ ] **Step 4: Commit**
```bash
git add src/components/quiz/QuizHeader.jsx src/components/quiz/QuizSidebar.jsx src/components/quiz/QuizFooter.jsx
git commit -m "feat(quiz): extract Quiz presentational components"
```

---

### Task 3: Refactor `Quiz.jsx` Container

**Files:**
- Modify: `src/pages/Quiz.jsx`

- [ ] **Step 1: Refactor `Quiz.jsx`**
Import `useQuizEngine` and the new presentational components. Replace the entire fat component logic. The container should only read from `useCourse`, `useSearchParams`, instantiate `useQuizEngine`, and assemble `<QuizHeader />`, `<QuizSidebar />`, `<QuestionRenderer />`, and `<QuizFooter />`.

- [ ] **Step 2: Verify Build**
Run `npm run lint` and `npm run build` to ensure no variables are missed.

- [ ] **Step 3: Commit**
```bash
git add src/pages/Quiz.jsx
git commit -m "refactor(quiz): convert Quiz page to thin container"
```

---

### Task 4: Extract `usePracticeResult` ViewModel

**Files:**
- Create: `src/hooks/usePracticeResult.js`

- [ ] **Step 1: Write the Hook implementation**
Create `src/hooks/usePracticeResult.js` extracting logic from `PracticeResult.jsx` (L20-99 and L139-158):
  - State: `resultData`, `diagnosisData`, `loading`, `generating`, `generateError`, `currentTextIndex`.
  - Computations: `accuracy`.
  - Effect: Refresh profile and evaluation if `accuracy >= 60`.
  - Effect: One-time delayed fetch (5s timeout) for `quizService.getResult`. Includes `setInterval` for text index progression.
  - Function: `handleGenerateWrongAnswerQuiz` (calls `personalizedResourcesService.generate` and navigates).
  - Function: `handleRetry`.
  - Ensure the hook returns all necessary state and functions.

- [ ] **Step 2: Commit**
```bash
git add src/hooks/usePracticeResult.js
git commit -m "feat(quiz): extract usePracticeResult hook"
```

---

### Task 5: Extract PracticeResult Presentational Components

**Files:**
- Create: `src/components/quiz/ResultLoadingState.jsx`
- Create: `src/components/quiz/ResultScoreBoard.jsx`
- Create: `src/components/quiz/QuestionReviewList.jsx`

- [ ] **Step 1: Create `ResultLoadingState.jsx`**
Extract the loading view with the typing animation. Props needed: `currentTextIndex`.

- [ ] **Step 2: Create `ResultScoreBoard.jsx`**
Extract the circular score chart and the top statistics cards. Props needed: `accuracy`, `resultData`, `diagnosisData`.

- [ ] **Step 3: Create `QuestionReviewList.jsx`**
Extract the detailed question-by-question review mapping (L226-360 in the original file). Props needed: `perQuestionResults`, `diagnosisData`.

- [ ] **Step 4: Commit**
```bash
git add src/components/quiz/ResultLoadingState.jsx src/components/quiz/ResultScoreBoard.jsx src/components/quiz/QuestionReviewList.jsx
git commit -m "feat(quiz): extract PracticeResult presentational components"
```

---

### Task 6: Refactor `PracticeResult.jsx` Container

**Files:**
- Modify: `src/pages/PracticeResult.jsx`

- [ ] **Step 1: Refactor `PracticeResult.jsx`**
Import `usePracticeResult` and the new presentational components. Assemble them into the final thin container. Remove all the old massive logic and DOM.

- [ ] **Step 2: Verify Build**
Run `npm run lint` and `npm run build` to ensure the application compiles correctly.

- [ ] **Step 3: Commit**
```bash
git add src/pages/PracticeResult.jsx
git commit -m "refactor(quiz): convert PracticeResult page to thin container"
```
