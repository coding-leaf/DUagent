I have gathered enough verified evidence across the module. Here is the complete artifact.

---

# Frontend (React 19) Codebase Review Report

Review scope: `frontend/` (React 19 + Vite 8 + Tailwind v4 + SWR 2 + Axios + Sonner, pure JSX).
Method: read every file under `frontend/src/{pages,components,hooks,context,api,utils}` plus `App.jsx`, `main.jsx`, `index.html`, `index.css`, `vite.config.js`, `eslint.config.js`, and cross-checked backend contracts (`backend/app/api/v1/*`, `backend/app/services/tutoring_stream_adapter.py`, `backend/app/api/deps.py`) for claims that depend on server behaviour. No files were modified. Commands a supervisor must run: `cd frontend && npm run lint`, `npm run test:unit`, `npm run build`, `npm run test:e2e` (node_modules is absent in this checkout, so nothing could be executed here).

## 1. Executive Summary & Architecture Health

**Overall verdict: structurally sound for a v2 delivery, with three real flow-breaking defects and well-contained tech debt. Not spaghetti, but the seams are in the wrong place.**

Strengths verified:

- **Layering is mostly honoured.** All HTTP goes through `frontend/src/api/client.js` (single Axios instance, base `/api/v1`, bearer interceptor, 10s timeout) and named service modules in `frontend/src/api/services/*` (15 modules). `grep -r "from 'axios'" frontend/src` returns only `api/client.js` and the two mock/test adapters. The one raw `fetch` (`api/services/chat.js:88`) is justified: SSE streaming cannot go through the JSON Axios instance.
- **Errors have a deliberate policy.** `api/client.js:30-50` centralises 403/5xx/network toasts, deliberately suppresses 401 toasts (covered by `api/__tests__/client.test.js:94-110`), and defers 4xx to callers to avoid "toast bombing" — commented intent matches the code.
- **SWR is the primary server-state mechanism** (24 `useSWR` call sites), with conditional keys (`null` when no course), `refreshInterval` functions that stop on terminal states (`hooks/useCatalog.js:102-150`, `hooks/useStudentProfile.js:20-27`, `hooks/usePersonalizedResources.js:18`), and optimistic `mutate` for deletes (`hooks/useCatalog.js:490-530`).
- **Reducers are extracted and tested.** `utils/chatStreamEvents.js` (pure SSE→message reducer) and `utils/chatContent.js` (JSON-envelope unwrapping) are pure modules with tests (`utils/__tests__/chatStreamEvents.test.js`, `chatContent.test.js`), and the workspace plugin registry (`components/workspace/PluginRegistry.js`) cleanly isolates artifact rendering.
- **40 test files** exist across hooks, components, utils, API client and 3 pages; `ChatContext.test.jsx` is genuinely valuable (draft-session retention, artifact restore, failed-workflow reduction).
- Presentational decomposition is real where it matters: `pages/Quiz.jsx` (155 lines) composes 6 quiz components; `CourseCatalogDrawer.jsx` (130 lines) is a thin shell over `hooks/useCatalog` + 8 section components.

Core architectural problems:

1. **Business logic lives in a 590-line hook.** `hooks/useCatalog.js` holds 16 `useState`, 8 `useSWR`, 7 `useEffect` and returns ~40 keys — it is the real "god component", just relocated out of JSX.
2. **`ChatContext.jsx` (392 lines) is four contexts in one**: session CRUD, SSE stream lifecycle, artifact bookkeeping, run-log buffer. Any change touches all four.
3. **Global state has three sources of truth.** `context/CourseContext.jsx:26-58` writes `activeCourseId` to React state, `localStorage.course_id`, and the `?course_id=` query param, then reconciles them in two effects (`:62-90`). This is the single largest source of ordering bugs.
4. **Two parallel error-message helpers** (`api/error.js#getApiErrorMessage` vs `utils/apiError.js#getErrorMessage`) with different FastAPI-validation handling, used inconsistently.
5. **Icon layer is a lossy shim.** `components/Icon.jsx` maps Material Symbols names to lucide names, but 22 names in use are unmapped and silently degrade to `HelpCircle`.

Scale facts (line counts): `useCatalog.js` 590 · `ChatContext.jsx` 392 · `Register.jsx` 384 · `common/MarkdownViewer.jsx` 347 · `PersonalizedResources.jsx` 299 · `Login.jsx` 294 · `TeacherConsole.jsx` 269 · `Dashboard.jsx` 264.

## 2. P0 Critical Issues (Render crashes, infinite SWR revalidation loops, broken routing)

### P0-1 — "停止生成" permanently disables the chat composer (no `isSending` reset on abort)

- **Location:** `frontend/src/context/ChatContext.jsx:168-173` (`cancelStream`), `:326-334` (`startStream`), `:252` (`setIsSending(false)` only inside `completeMessage`); `frontend/src/api/services/chat.js:139-143`; `frontend/src/components/chat/ChatArea.jsx:35`, `:179-186`.
- **Evidence:** The stop button calls `cancelStream()` only; that function aborts the fetch and nulls the ref, but never calls `setIsSending(false)`. In the real-API path, abort is swallowed:
  ```js
  // api/services/chat.js:139
  if (err.name === 'AbortError') { console.log('Fetch aborted'); } else { onError(err); }
  ```
  `isSending` is therefore only cleared by `completeMessage`, which only fires on `workflow_completed` / `workflow_failed` / `onError`. Since abort never reaches `onError`, `isSending` stays `true`. `ChatArea.handleSendMessage` (`:35`) and `sendMessage` (`ChatContext.jsx:341`) both early-return on `isSending`, so the user can neither send nor retry; the composer keeps rendering the red stop button (`ChatArea.jsx:179-186`). Only "新对话" (`resetConversation`, `ChatContext.jsx:183-196`) recovers the UI. In mock mode the same happens because `clearInterval` returns without emitting a terminal event.
- **Impact:** one click of the primary escape hatch bricks the AI-chat page for the rest of the session.
- **Smallest fix:** in `cancelStream`, call `setIsSending(false)` and mark the in-flight assistant message as aborted (e.g. `setMessages(prev => updateTargetMessage(prev, targetIdRef.current, m => ({ ...m, loading: false })))`), or have `chat.js` call `onError(Object.assign(new Error('aborted'), { aborted: true }))` and let `completeMessage` run in a non-error branch. Add a regression test to `ChatContext.test.jsx` (there is currently no cancel test).

### P0-2 — 401 on failed login destroys the form and the error message (bad-password path is unusable)

- **Location:** `frontend/src/api/client.js:31-37`; `frontend/src/pages/Login.jsx:44-83`; backend contract `backend/app/api/v1/auth.py:117-121`.
- **Evidence:** The backend returns **HTTP 401** for wrong credentials (`auth.py:119-121`, `detail={"code":40100,"message":"邮箱或密码错误"}`). The Axios interceptor treats *every* 401 as an expired session:
  ```js
  // api/client.js:32
  if (status === 401) { localStorage.removeItem('access_token'); window.location.href = '/login'; }
  ```
  `window.location.href` triggers a full document navigation, so `Login.jsx:79-81`'s `setError(getApiErrorMessage(err, '登录失败'))` renders into a tree that is being discarded. `App.jsx:36` then redirects `/login` → `/`, remounting a fresh `Login` with empty `email`/`password`/`captchaCode` state. Net user experience: "I typed the wrong password, the page reloaded, all my fields are gone, and no error was shown."
- **Impact:** the single most-used failure path of the entry point has no error feedback; also silently breaks any future endpoint that legitimately returns 401 for authentication-in-endpoint semantics.
- **Smallest fix:** exempt the auth endpoints from the global redirect, e.g. in `client.js` skip the redirect when `error.config?.url?.includes('/auth/login')` (or set a per-request flag `{ skipAuthRedirect: true }` in `api/services/auth.js#login`). Keep redirect for other 401s. Add a case to `api/__tests__/client.test.js`.

### P0-3 — Teacher console "退出登录" does not log out

- **Location:** `frontend/src/pages/TeacherConsole.jsx:22-24` and `:193-202`.
- **Evidence:** `const { user } = useAuth();` — `logout` is never destructured. The button labelled 退出登录 executes only `onClick={() => navigate('/')}`. `localStorage.access_token` is untouched, `AuthContext.user` stays populated, and any `/teacher` navigation immediately re-authorises (no reload occurs, because it is a client-side route change). Compare `TeacherStudentReport.jsx:23,30-32` which correctly does `const { user, logout } = useAuth()` + `logout(); navigate('/')`.
- **Impact:** a shared-machine logout failure on a role-gated console — security-relevant, trivially reproducible.
- **Smallest fix:** `const { user, logout } = useAuth();` and `onClick={() => { logout(); navigate('/'); }}`.

### P0-4 (conditional) — `crypto.randomUUID()` throws on non-secure origins

- **Location:** `frontend/src/context/ChatContext.jsx:34,343`; `utils/chatStreamEvents.js:104,113,141`; `hooks/useRunLogs.js:8`.
- **Evidence:** `crypto.randomUUID` is only exposed in **secure contexts** (HTTPS, `localhost`, `127.0.0.1`). `vite.config.js:8` pins dev to `127.0.0.1` (fine), but the built SPA is served by the FastAPI static mount (`backend/app/static_site.py`) — a campus deployment on `http://<lan-ip>` lands in a non-secure context where `crypto.randomUUID` is `undefined`. The very first `sendMessage` (`ChatContext.jsx:343`) then throws `TypeError` inside the click handler, so the user turn is never appended and the stream never starts; `useRunLogs.appendRunLog` (`:8`) throws the same way on every stream event.
- **Impact:** total chat breakage on plain-HTTP deployment. Marked conditional because it depends on the deployment scheme, not on code alone.
- **Smallest fix:** add `utils/id.js` with `export const uid = () => globalThis.crypto?.randomUUID?.() ?? \`${Date.now().toString(36)}-${Math.random().toString(36).slice(2,10)}\`;` and replace all five call sites.

**Explicitly checked and found NOT broken** (so they are not listed as P0): no infinite SWR revalidation loop exists — `useCatalog`'s task-transition effects (`:232-296`) call `mutateAll()`, but `activeTask` identity only changes with the separate `taskStatus/*` key, so the effect converges; `refreshInterval` correctly returns `0` on terminal states in all four pollers. Routing is coherent: all 16 routes in `App.jsx:35-59` map to real files, `/login`→`/` produces a terminating redirect, and every role branch in `ProtectedRoute.jsx:21-31` targets an existing route.

## 3. P1 High Tech-Debt & Spaghetti Code

### P1-1 — `hooks/useCatalog.js` (590 lines) is a god hook: 16 state atoms, 8 SWR keys, 40-key return
`useState` at `:70-95`, `useSWR` at `:33,43,53,63,98,112,126,140`, derivations at `:377-450`, handlers at `:362-537`, return object at `:541-589`. `CourseCatalogDrawer.jsx:14-37` destructures **37 properties** from it. Four near-identical task-transition effects (`:232-296`) duplicate `setIngesting/generating/...` + `mutateAll()` + `onChanged()`; four near-identical pollers (`:98-150`) differ only in key/fallback type.
**Smallest fix (incremental, no rewrite):** extract `useTaskPolling(taskId, kind)` returning `{task, processing, error}` (kills 4×2 duplicated blocks), then split the hook into `useCatalogMaterials`, `useCatalogGeneration`, `useCatalogKnowledgeGraph`. Add one `useCatalog.test.js` case per extracted hook (the existing `hooks/__tests__/useCatalog.test.js` already mocks the service layer, so refactoring cost is low).

### P1-2 — `context/ChatContext.jsx` (392 lines) mixes four concerns; one impure state updater
Session CRUD (`:200-228`), SSE handlers (`:230-323`), artifact hiding/restoring (`:67-80`), run logs (`:65`), and the `messages` reducer wiring all share one provider. Additionally `hideArtifact` calls `setActiveArtifactId` **inside** the `setHiddenArtifactIds` updater (`:70-74`) — an impure updater that React 19 StrictMode invokes twice. It happens to be idempotent today, but it is exactly the class of bug that becomes a render loop after the next edit.
**Smallest fix:** move `{workspaceArtifacts, activeArtifactId, hiddenArtifactIds, hide/restore}` into a `WorkspaceArtifactsProvider` and compute the next active id from the derived visible list in the event handler instead of inside an updater.

### P1-3 — 22 icon names silently render a generic "?" (`Icon.jsx` lossy shim)
`components/Icon.jsx:124` falls back to `'HelpCircle'` for unknown names, and `:127` returns `null` if the lucide export is missing. Scanning every JSX `Icon name=` and `icon: '...'` literal against `materialToLucide` (`Icon.jsx:5-115`) yields these **used but unmapped** names:

| Icon name | Confirmed usage |
|---|---|
| `chevron_left` | `components/chat/SidebarHistory.jsx:87`, `SidebarResources.jsx:125` (both collapse handles) |
| `folder_open` | `components/FeedbackStatus.jsx:16` (every empty state) |
| `download` | `components/common/MarkdownViewer.jsx:211`, `workspace/plugins/MarkdownViewer.jsx:111` |
| `person` | `components/chat/ChatMessage.jsx:79` (user avatar) |
| `edit` | `components/chat/ChatArea.jsx:132` |
| `chat_bubble_outline` | `components/chat/SidebarHistory.jsx:57` |
| `groups` | `pages/PersonalizedResourceGenerate.jsx:73`, `components/personalized/AgentTeamProgress.jsx:15`, `teacher/StudentMonitoringSection.jsx:26` |
| `upload_file` | `components/admin/catalog/MaterialUploadSection.jsx:17` |
| `verified` | `components/profile/LearningStateCard.jsx:62`, `AgentTeamProgress.jsx` STAGES |
| `check_circle_outline` | `pages/TeacherStudentReport.jsx:127` |
| `schedule` | `pages/LearningEffects.jsx:44` |
| `explore` | `components/learning/PathVisualizer.jsx:127` |
| `sync` | `components/profile/LearningArchiveCard.jsx:36`, `report/KnowledgeCoordinatesCard.jsx:33` |
| `help`, `radio_button_unchecked` | `components/profile/KnowledgeRadarCard.jsx:58,33` (dynamic states) |
| `code_blocks`, `calendar_month` | `components/chat/ChatEmptyState.jsx:8-24` |
| `video_library` | `components/chat/SidebarResources.jsx:80` |
| `speed` | `components/quiz/QuizSidebar.jsx:14` |
| `fact_check` | `components/personalized/AgentTeamProgress.jsx:7` |
| `warning_amber` | `components/chat/ToolCallCard.jsx:26` |
| `radio_button_checked`, `check_box` | `components/personalized/GenerateModal.jsx:6-7` |

**Smallest fix:** add the 22 entries (`chevron_left: 'ChevronLeft'`, `download: 'Download'`, `sync: 'RefreshCw'`, `verified: 'BadgeCheck'`, …) and, during dev, `console.warn` on fallback so the map cannot silently rot again.

### P1-4 — Dashboard issues one `/resources` request per keystroke and double-filters server + client
`pages/Dashboard.jsx:43-68`: `fetchResources` depends on `searchTerm`, and `useEffect(..., [fetchResources])` re-runs on every change; `Navbar`'s search input writes straight into `searchTerm` (`Navbar.jsx:107-116` → `Dashboard.jsx:126`). No debounce (contrast `admin/UserManagementPanel.jsx:41-46`, which debounces 500 ms). Each keystroke also flips `loading` (`:46`), replacing the grid with a spinner and collapsing layout. Meanwhile `:71-85` re-filters the same term client-side, and the request already sends `keyword` (`:50`) — two filters, one behaviour.
**Smallest fix:** drop `keyword` from the request and rely on client filtering for a 50-item page (removes `searchTerm` from the callback deps entirely), or debounce 300 ms if server search is required. Remove `selectedType` from the type filter duplication in `RESOURCE_TYPES`/`TYPE_MAP` (`:8-28`).

### P1-5 — Practice-result page fabricates quiz statistics when history is lost
`hooks/usePracticeResult.js:44-60`: if `resultData` is absent (the common case after a page refresh, since `location.state` is lost), the hook synthesises a result from `latest_quiz.score` with **hard-coded** `total_count: 10` and `correct_count: Math.round(score/100*10)`. `accuracy` (`:26`) is then derived from fabricated denominators, and `PracticeResult.jsx:92` feeds `per_question_results: []` to `QuestionReviewList`. A user who refreshes sees invented counts presented as facts.
**Smallest fix:** do not synthesise; render a "请重新作答以查看逐题解析" empty state when `per_question_results` is missing, using server-provided `total_count` if the backend supplies it. Also remove the artificial 5 s `setTimeout(fetchDiagnosis, 5000)` at `:82` — it is unexplained latency in front of the only data fetch.

### P1-6 — Silent failure cluster: state changes that cannot report failure
- `pages/StudentProfile.jsx:288-291`: `handleGoalChange` optimistically sets `localDriveIntentType` then `profileService.updateLearningGoal(...).catch(() => {})` — on failure the UI keeps the new goal forever, with no toast and no rollback (compare the correctly-implemented rollback in `handleGuidanceChange`, `:255-274`).
- `context/ChatContext.jsx:148-156`: `getHistory(...).catch(console.error)` — a failed history load leaves an empty conversation pane with zero user-facing feedback.
- `hooks/usePracticeResult.js:30`: `refreshEvaluation(...).catch(() => {})` and `ProfileService.refreshProfile(...).catch(() => {})` — background refreshes fail invisibly, so "学习效果" silently stays stale.
- `hooks/useCodeSandboxExecution.js:20-33`: the `useSWR` result destructures only `data`; there is no `error` handling, and `isRunning` is only cleared when a **non-processing** task arrives. If the judge task 404s or the poll errors, `isRunning` stays `true` forever and the 运行代码 button (`CodeSandboxCard.jsx:160`) is permanently disabled.
- `api/services/learningActivity.js:11-16` swallows to `console.warn` — acceptable for telemetry, but it means the study-tracking feedback loop can be dead without anyone noticing.

**Smallest fix:** standardise on `toast.error(getErrorMessage(err, '<action> 失败'))` for user-initiated mutations (Sonner is already mounted in `App.jsx:30`), and add `error` + `onError` to `useCodeSandboxExecution`'s SWR to reset `isRunning`.

### P1-7 — `?course_id=` triple source of truth
`context/CourseContext.jsx`: `activeCourseId` is read at first load from `URLSearchParams` then `localStorage` then first course (`:31-46`), written to both (`:48-50`), re-synced from `location.search` in a second effect (`:70-88`), and rewritten via `navigate({..., search})` in `changeCourse` (`:92-104`). The two effects are ordered by React's effect sequence and each guards with a `setTimeout(0)` (`:52`, `:73`) — a code smell that hides double-render races. Additional inconsistency: `TeacherConsole`/`TeacherStudentReport` re-parse `location.search` themselves (`TeacherStudentReport.jsx:22-24`) instead of using the context.
**Smallest fix:** make the URL the single source of truth (`useSearchParams`); keep `localStorage` only as the initial redirect target; delete the second sync effect and both `setTimeout(0)` wrappers.

### P1-8 — Two competing error-message helpers
`api/error.js` (Handles FastAPI `detail: [{loc,msg,type,ctx}]` arrays, with per-field Chinese labels) vs `utils/apiError.js` (handles only string `detail` / `detail.message` / `message`). Consumers: `Login.jsx:3`, `Register.jsx` use the former; everything else (`useCatalog`, all admin panels, `usePersonalizedResources`) uses the latter. Consequence: 422 validation arrays from the admin panels render as generic "请求失败", while the same error on the register form renders "密码至少 8 个字符".
**Smallest fix:** merge into `utils/apiError.js` (keep the `formatValidationError` logic, keep the `getErrorMessage` name), re-point `Login`/`Register`, delete `api/error.js` (its only other consumer is `pages/Login.jsx`). `utils/__tests__/apiError.test.js` already exists to extend.

### P1-9 — `rehypeRaw` renders model-generated HTML unsanitised
`components/common/MarkdownViewer.jsx:4` and `:339` pass `rehypePlugins={[rehypeRaw]}` for content that is streamed directly from the agent (`ChatMessage.jsx:145-160` renders `extractModelText(part.content)`). `grep` for `bleach|sanitize|nh3|html.escape` across `backend/app` returns **no matches**, so nothing upstream sanitises it either. Raw `<img onerror>` / `<script>`-adjacent payloads in LLM output become live DOM. `dangerouslySetInnerHTML` at `:164` is separately mitigated by `securityLevel: 'strict'` in `utils/mermaid.js:5-11` — but markdown is not.
**Smallest fix:** add `rehype-sanitize` (with the GitHub schema) after `rehypeRaw`, or drop `rehypeRaw` if `details/summary` passthrough is not required.

### P1-10 — No application-level ErrorBoundary
`grep -r "ErrorBoundary" frontend/src` returns only `MermaidErrorBoundary` (`common/MarkdownViewer.jsx:13`), scoped to Mermaid rendering. A malformed artifact prop reaching `AgentWorkspace.jsx:47-60` (which renders `PluginRegistry[activeArtifact.type]` with arbitrary `props`), or a `.length` on a null field, unmounts the entire tree to a blank page.
**Smallest fix:** a single `AppErrorBoundary` in `main.jsx`/`App.jsx` around `<Routes>`, plus keeping the existing Mermaid boundary.

## 4. P2 KISS Simplification Opportunities

### Dead files / assets (verified by exhaustive import grep)
| Path | Lines | Evidence of deadness |
|---|---|---|
| `src/services/catalogService.js` (+ `.test.js`) | 141 + 160 | Duplicate of `src/api/services/catalog.js`; the only importer is its own test. `grep "from '.*services/catalogService'"` → **no matches** in app code |
| `src/components/personalized/GenerateModal.jsx` | 259 | No importer anywhere (`grep` across `*.{js,jsx,html,cjs}`) |
| `src/components/effects/EffectsSuggestionsCard.jsx` | 44 | No importer; superseded by `EffectsSummaryCard` |
| `src/components/chat/SidebarResources.jsx` | 131 | No importer; `AIChat.jsx:38-45` renders only `SidebarHistory`/`AgentWorkspace`/`ChatArea` |
| `src/components/quiz/CodingQuestionCard.jsx` | 37 | No importer; `QuestionRenderer.jsx:16` routes unknown types to `UnsupportedQuestionCard`. (Consistent with backend: `backend/app/api/v1/quiz.py:62` only serves `single_choice`/`multi_choice`.) |
| `src/assets/react.svg`, `src/assets/vite.svg`, `public/icons.svg`, `public/test.html` | — | Zero `assets/` or `icons.svg` references in `src/` |
| `fix_aichat.py`, `patch_aichat.py`, `update_icons.py`, `test_mermaid.cjs`, `test_mermaid2.cjs`, `test_regex.js`, `test_regex2.cjs` | — | One-off codemod/scratch scripts; `update_icons.py:20` hard-codes another developer's absolute path `/home/yezisama/workspace/...`, which will not run anywhere else |
| `前端页面字段与布局结构数据报告.md` | — | Generated survey artefact at package root |

Removing `catalogService.js` + its test, `GenerateModal`, `EffectsSuggestionsCard`, `SidebarResources`, `CodingQuestionCard` deletes ~610 lines with zero behavioural risk. Note `frontend/src/services/catalogService.test.js` also duplicates `src/api/services/__tests__/catalog.test.js` (same 15 assertions), so the suite shrinks without losing coverage.

### Tailwind v4 cleanup — ~90 no-op utility classes
`src/index.css` `@theme` defines only `--color-*`, `--radius-*`, `--width-*`, `--spacing-*` and `--font-*`. There is **no `--text-*` scale** (`grep "--text-" index.css` → no matches). Therefore `text-h1`, `text-h2`, `text-h3`, `text-body-md`, `text-body-lg`, `text-label-sm`, `text-title-md` generate **nothing**; only the paired `font-h1`/`font-body-md` (font-family) survives. Confirmed consumers: `LearningPath.jsx:28`, `LearningEffects.jsx:36-54`, `TeacherStudentReport.jsx:74-80`, `Quiz.jsx:105`, `PathVisualizer.jsx:27-41`, `NodeResourcePanel.jsx:27`, `PracticeResult.jsx:81-130`, `PersonalizedResources.jsx:74-287`, `Login.jsx:163-264`, `Register.jsx:181-374`, `StudentProfile.jsx:170`, `ProtectedRoute.jsx:13`, plus most of `components/{quiz,profile,report,personalized}`.
Fix: either add `--text-h1: 2rem; --text-h2: 1.5rem; --text-h3: 1.25rem; --text-body-md: 0.875rem; --text-label-sm: 0.75rem;` to `@theme`, or delete the dead classes and rely on the explicit `text-xl`/`text-sm` already present in most of those lines. Also delete `border-slate-150` (`workspace/plugins/codeSandbox/CodeSandboxCard.jsx:204`) — not a Tailwind palette step.

### Dead CSS and stale font assets
- `index.css`: `.radar-shape` (`:117`), `.abstract-pattern` (`:118-121`), `.chat-bubble-ai` (`:123-127`), `.chat-bubble-user` (`:128-131`) have **zero** consumers (`grep -r "radar-shape\|abstract-pattern\|chat-bubble"` → only `index.css`).
- `.material-symbols-outlined` (`:80-83`) is retained purely so `Icon.jsx:118` can strip it; the app renders lucide components, so `index.html:9`'s `Material+Symbols+Outlined` stylesheet is a pure dead request. Drop the `<link>` and the CSS block once the `material-symbols-outlined` class strings are removed from call sites.

### Inconsistent/duplicated helpers
- `hooks/useLearningPath.js:6-11` re-declares `fetcherWrapper` locally, diverging from `utils/fetcher.js` — import the shared one.
- `hooks/useStudentReport.js:7-15` hand-rolls code checking instead of `fetcherWrapper`; `hooks/useTeacherConsoleData.js:10` uses the odd key `['api','teaching','classes']` while every other key is `['domain', ...ids]`. Centralise keys in `api/services/*` (e.g. `taskService.statusKey(id)`) so `mutate` calls cannot drift.
- `hooks/useRecommendedResources.js:8` and `pages/Dashboard.jsx:47` both hit `GET /resources` with different keys/params; one `useResources(courseId, {pageSize})` would dedupe SWR caching.

### Duplicated JSX
`Login.jsx` (294) and `Register.jsx` (384) repeat the entire left marketing panel (gradient blobs, brand block, feature list, `glass-panel` card, footer with `href="#"` links) — roughly 100 near-identical lines. Extract `components/auth/AuthShell.jsx`.

### Dead UI controls (present but inert)
- `Navbar.jsx:120-123`: 通知 button has no `onClick`.
- `Navbar.jsx:130-136`: user avatar `src` is a hard-coded `https://lh3.googleusercontent.com/aida-public/...` URL — an external, likely-expired asset instead of `user` data.
- `Login.jsx:14,231-238`: the 记住我 checkbox is stored in `rememberMe` and never read, so it implies persistence that does not exist.
- `Login.jsx:264`: 隐私政策/服务条款 are `href="#"`.
- `TeacherStudentReport.jsx:76-82`: two permanently `disabled` buttons rendered as live-looking actions ("导出报告 (暂不可用)").
- `StudentProfile.jsx:399`: bottom-nav centre FAB renders a `+` icon with no handler.
- `MarkdownViewer.jsx:211` / `workspace/plugins/MarkdownViewer.jsx:111`: the download link puts the bearer token in a query string (`?token=...`) — accepted by `backend/app/api/deps.py:43-71` via `get_download_user`, but it leaks the JWT into browser history/referrers. Prefer a short-lived signed URL.

### UX-consistency nits
- `pages/PersonalizedResources.jsx:166,171`: `window.confirm` + `alert('删除失败，请稍后重试')` inside an app that already mounts Sonner and uses `FeedbackStatus`. Same for `SidebarHistory.jsx:63`, `UserManagementPanel.jsx:53`, `RegistrationCodesPanel.jsx:54`. Replace with a shared `<ConfirmDialog>` + `toast.error`.
- `pages/PersonalizedResources.jsx:252,256`: `groupQuestionsByKp(items)` is computed twice per render, and `items.filter(...)` runs four times (`:243,245,270,274,282,286`). Derive once with `useMemo` (`items`, `filterSource`) — trivial KISS win in a 299-line page.
- `pages/PersonalizedResources.jsx:113`: `q.content.length` assumes non-null `content`; backend guarantees it (`backend/app/models/quiz.py:28`), but a guard keeps the list from blanking the page.
- `TeacherStudentReport.jsx:22-24` and `TeacherConsole.jsx:107-110` read `course_id`/`student_id` from raw query strings rather than the router's `useSearchParams`.
- `hooks/useQuizEngine.js:78-84` calls `setState` during render (guarded by a ref) to reset answers on `quiz_id` change — works, but `key={quiz_id}` on the question subtree would be idiomatic and remove the eslint-purity exception.
- ~14 `eslint-disable react-hooks/set-state-in-effect` suppressions (`ChatContext.jsx:97,143`, `useLearningEffects.js:27,110`, `useStudentProfile.js:31`, `StudentProfile.jsx:70,90`, `TeacherConsole.jsx:49,57,87,93`, `NodeResourcePanel.jsx:13`, `CourseContext.jsx:65`, `CodeSandboxCard.jsx:149`). Each marks a state mirror that could be derived; they are the best shortlist for future simplification.

## 5. Actionable Frontend Refactoring Roadmap

### Stage 0 — Stop the bleeding (1–2 days, blocks release)
1. **P0-1** `ChatContext.cancelStream` → clear `isSending` and mark the message aborted; add a cancel test to `ChatContext.test.jsx`.
2. **P0-3** `TeacherConsole` logout → call `logout()` before `navigate('/')`.
3. **P0-2** `client.js` 401 handler → skip the hard redirect for `/auth/login` (per-request opt-out in `api/services/auth.js`); extend `api/__tests__/client.test.js`.
4. **P0-4** add `utils/id.js#uid()` and replace the five `crypto.randomUUID()` call sites.
5. **P1-9** add `rehype-sanitize` (or drop `rehypeRaw`) in `common/MarkdownViewer.jsx`.
6. Add `AppErrorBoundary` in `main.jsx`.
7. Verification gate: `npm run lint && npm run test:unit && npm run build`, plus a manual pass over: 登录失败提示 / AI 对话停止生成 / 教师退出登录 / 刷新练习结果页.

### Stage 1 — Correctness and consistency (3–5 days)
8. **P1-5** remove fabricated quiz stats + the 5 s artificial delay in `usePracticeResult`.
9. **P1-6** convert the silent `.catch(() => {})` sites to `toast.error(getErrorMessage(...))`; add `error`+`onError` to `useCodeSandboxExecution`'s SWR so `isRunning` cannot stick.
10. **P1-4** de-duplicate Dashboard filtering (drop the `keyword` request or add a 300 ms debounce), remove `searchTerm` from the fetch deps.
11. **P1-3** complete the `materialToLucide` map (22 entries) + dev-only `console.warn` on fallback.
12. **P1-8** merge the two error helpers into `utils/apiError.js`, delete `api/error.js`.

### Stage 2 — Dead-code and CSS sweep (1–2 days, mechanical, high payoff)
13. Delete `src/services/catalogService.js` + `catalogService.test.js`, `GenerateModal.jsx`, `EffectsSuggestionsCard.jsx`, `SidebarResources.jsx`, `CodingQuestionCard.jsx`.
14. Delete `src/assets/*.svg`, `public/icons.svg`, `public/test.html`, the 7 root codemod scripts, and the generated `.md` report.
15. Remove the unused `@theme`-orphan classes (`text-h1|h2|h3|body-md|body-lg|label-sm|title-md`) or define the `--text-*` tokens; delete `border-slate-150`; delete `.radar-shape` / `.abstract-pattern` / `.chat-bubble-*`; drop the Material Symbols `<link>` + class.
16. Remove inert controls (`Navbar` 通知 + hard-coded avatar, `Login` 记住我, disabled export/feedback buttons, dead FAB).
17. Gate: `npm run build` bundle-size delta + `npm run test:unit`.

### Stage 3 — Structural decomposition (1–2 weeks, behind the test suite)
18. Extract `useTaskPolling(taskId, kind, {open})` from `useCatalog.js`, collapsing the four duplicated pollers and four near-identical transition effects; then split the hook by concern (`materials` / `generation` / `kg`). Target: `useCatalog.js` under 200 lines, `CourseCatalogDrawer` destructuring under 15 keys.
19. Split `ChatContext` into `SessionProvider` (list/active/history), `ChatStreamProvider` (send/abort/reduce), `WorkspaceArtifactsProvider` (artifact+hidden+active) and move `hideArtifact`'s cross-state update out of the state updater.
20. **P1-7** make the URL the single source of truth for `activeCourseId` (`useSearchParams`), delete the second sync effect and both `setTimeout(0)` wrappers; make `TeacherConsole`/`TeacherStudentReport` consume the context.
21. Extract `components/auth/AuthShell.jsx` to absorb the ~100 duplicated lines between `Login`/`Register`.
22. Centralise SWR keys in `api/services/*` and adopt `useResources(...)` for both `Dashboard` and `useRecommendedResources`.

### Stage 4 — Hardening (ongoing)
23. Replace `window.confirm`/`alert` with a shared `ConfirmDialog` + Sonner toasts across the 5 sites.
24. Replace the token-in-query download links with short-lived signed URLs.
25. Remove `eslint-disable react-hooks/set-state-in-effect` one site at a time (14 sites listed in §4) by deriving the state instead of mirroring it.
26. Add the missing tests that would have caught Stage-0 bugs: chat abort, 401-on-login, teacher logout, `useCodeSandboxExecution` error path, and one routing smoke test per role in `App.jsx`.

### Merge verdict: **BLOCK** — P0-1 (chat composer locked after stop), P0-2 (login failure reloads with no message), and P0-3 (teacher logout does not clear the session) are all reachable in normal use; P0-4 must be confirmed against the intended deployment scheme before release. Everything in Stages 1–4 can land after the Stage-0 patch without blocking.