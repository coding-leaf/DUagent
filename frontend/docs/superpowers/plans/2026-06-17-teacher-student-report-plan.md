# TeacherStudentReport Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the monolithic `TeacherStudentReport.jsx` into MVVM architecture by extracting data fetching to a custom hook using SWR, and splitting the UI into 9 independent presentational components.

**Architecture:** MVVM. A single hook (`useStudentReport`) acts as the ViewModel to fetch and cache data. The container (`TeacherStudentReport`) orchestrates dumb UI components which receive their data via props.

**Tech Stack:** React, React Router, SWR.

---

### Task 1: Extract `useStudentReport` ViewModel Hook

**Files:**
- Create: `src/hooks/useStudentReport.js`
- Test: `src/hooks/__tests__/useStudentReport.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
// src/hooks/__tests__/useStudentReport.test.js
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import useStudentReport from '../useStudentReport';
import { teachingService } from '../../api/services/teaching';

vi.mock('../../api/services/teaching', () => ({
  teachingService: {
    getStudentReport: vi.fn()
  }
}));

describe('useStudentReport', () => {
  it('does not fetch when classId or studentId is missing', () => {
    const { result } = renderHook(() => useStudentReport(null, 's123'));
    expect(teachingService.getStudentReport).not.toHaveBeenCalled();
    expect(result.current.reportData).toBeUndefined();
  });

  it('fetches and returns data correctly', async () => {
    teachingService.getStudentReport.mockResolvedValue({ code: 200, data: { name: 'Test Student' } });
    const { result } = renderHook(() => useStudentReport('c1', 's1'));
    
    await waitFor(() => {
      expect(result.current.reportData).toEqual({ name: 'Test Student' });
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:unit src/hooks/__tests__/useStudentReport.test.js`
Expected: FAIL with "useStudentReport is not a function"

- [ ] **Step 3: Write minimal implementation**

```javascript
// src/hooks/useStudentReport.js
import useSWR from 'swr';
import { teachingService } from '../api/services/teaching';

export default function useStudentReport(classId, studentId) {
  const key = classId && studentId ? ['studentReport', classId, studentId] : null;
  
  const { data, error, isLoading } = useSWR(key, async ([, cid, sid]) => {
    const res = await teachingService.getStudentReport(cid, sid);
    if (res.code !== 200) throw new Error(res.message || 'Failed to fetch report');
    return res;
  });

  return {
    reportData: data?.data,
    isLoading,
    error
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:unit src/hooks/__tests__/useStudentReport.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useStudentReport.js src/hooks/__tests__/useStudentReport.test.js
git commit -m "feat(report): extract useStudentReport hook with SWR"
```

### Task 2: Create ReportHeader and ProfileBanner Components

**Files:**
- Create: `src/components/report/ReportHeader.jsx`
- Create: `src/components/report/ProfileBanner.jsx`

- [ ] **Step 1: Write `ReportHeader.jsx`**

```javascript
// src/components/report/ReportHeader.jsx
import { useNavigate } from 'react-router-dom';
import Icon from '../Icon';

export default function ReportHeader({ courseName, user }) {
  const navigate = useNavigate();
  return (
    <header className="fixed top-0 w-full z-50 flex justify-between items-center px-gutter h-20 bg-white border-b border-outline-variant shadow-sm font-['Public_Sans'] antialiased">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-on-surface">{courseName}</h1>
        <span className="px-2 py-1 bg-surface-container-high text-primary font-bold text-xs rounded uppercase">教学控制台</span>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-cyan-500/10 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-sm">
            {(user?.real_name || user?.username || '教').charAt(0)}
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-on-surface">{user?.real_name || user?.username || '教师'}</span>
            <span className="text-[10px] text-outline uppercase tracking-wider">
              {{ teacher: '教师', admin: '管理员' }[user?.role] || '教师'}
            </span>
          </div>
        </div>
        <div className="h-8 w-[1px] bg-outline-variant"></div>
        <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-error hover:bg-error-container/20 rounded-lg transition-colors cursor-pointer" onClick={() => navigate('/')}>
          <Icon name="logout" className="material-symbols-outlined text-sm"/>
          退出登入
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Write `ProfileBanner.jsx` with Initials Avatar**

```javascript
// src/components/report/ProfileBanner.jsx
export default function ProfileBanner({ report, classId }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm flex flex-col md:flex-row items-center gap-6">
      <div className="w-20 h-20 rounded-full overflow-hidden bg-cyan-500/10 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-3xl flex-shrink-0">
        {(report?.student?.real_name || report?.student?.student_id || '学').charAt(0)}
      </div>
      <div className="flex-grow text-center md:text-left">
        <h2 className="text-2xl font-bold text-on-surface mb-1">{report?.student?.real_name || report?.student?.student_id || '学生'}</h2>
        <p className="text-sm text-secondary">学号: {report?.student?.student_id || '未知'} · 班级ID: {classId}</p>
      </div>
      <div className="bg-primary/5 border border-primary/20 rounded-xl px-6 py-4 flex flex-col items-center">
        <span className="text-2xl font-black text-primary">待定</span>
        <span className="text-[10px] text-secondary font-bold uppercase tracking-wider">评分口径待定</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/report/ReportHeader.jsx src/components/report/ProfileBanner.jsx
git commit -m "feat(report): create ReportHeader and ProfileBanner with initials avatar"
```

### Task 3: Create Stats and Progress Cards

**Files:**
- Create: `src/components/report/QuizStatsMetrics.jsx`
- Create: `src/components/report/PathProgressCard.jsx`
- Create: `src/components/report/ModalityPreferenceCard.jsx`

- [ ] **Step 1: Write `QuizStatsMetrics.jsx`**

```javascript
// src/components/report/QuizStatsMetrics.jsx
import Icon from '../Icon';

export default function QuizStatsMetrics({ stats }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="assessment" className="material-symbols-outlined text-primary text-xl"/>
        在线测试统计 (Quiz Stats)
      </h3>
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-surface-container rounded p-3 text-center">
          <span className="text-xl font-bold text-on-surface block">{stats?.total_attempts || 0}</span>
          <span className="text-[10px] text-secondary">总测试</span>
        </div>
        <div className="bg-surface-container rounded p-3 text-center">
          <span className="text-xl font-bold text-on-surface block">{stats?.avg_score || 0}%</span>
          <span className="text-[10px] text-secondary">平均分</span>
        </div>
        <div className="bg-surface-container rounded p-3 text-center">
          <span className="text-xl font-bold text-on-surface block">{(stats?.avg_time_spent || 0) < 60 ? '< 1m' : `${Math.round((stats.avg_time_spent) / 60)}m`}</span>
          <span className="text-[10px] text-secondary">均时</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `PathProgressCard.jsx`**

```javascript
// src/components/report/PathProgressCard.jsx
import Icon from '../Icon';

export default function PathProgressCard({ progress }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="account_tree" className="material-symbols-outlined text-primary text-xl"/>
        学习路径进度 (Path Progress)
      </h3>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-secondary mb-1">当前学习节点</p>
          <p className="text-base font-bold text-on-surface truncate max-w-[120px]">{progress?.current_node || '暂无活跃节点'}</p>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-xl font-black text-primary">
            {progress?.completed_nodes || 0} / {progress?.total_nodes || 0}
          </span>
          <span className="text-[10px] text-secondary">已完成节点</span>
        </div>
      </div>
      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
        <div
          className="bg-primary h-full transition-all duration-300"
          style={{ width: `${((progress?.completed_nodes || 0) / (progress?.total_nodes || 1)) * 100}%` }}
        ></div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `ModalityPreferenceCard.jsx`**

```javascript
// src/components/report/ModalityPreferenceCard.jsx
import Icon from '../Icon';

export default function ModalityPreferenceCard({ preferences }) {
  const modalLabels = { video_animation: '视频/动画', chart_logic: '图表/逻辑', text_analysis: '文本阅读', code_practice: '代码练习', formula_derivation: '公式推导' };
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="psychology" className="material-symbols-outlined text-primary text-xl"/>
        模态偏好 (Modal Preference)
      </h3>
      <div className="flex flex-wrap gap-2">
        {preferences && preferences.length > 0 ? (
          preferences.map((p, idx) => (
            <span key={idx} className="px-3 py-1.5 bg-cyan-50 text-cyan-700 text-xs font-bold rounded-lg border border-cyan-100 flex items-center gap-1">
              <span className="text-[10px] opacity-60">#{idx + 1}</span> {modalLabels[p] || p}
            </span>
          ))
        ) : (
          <p className="text-xs text-outline italic text-center py-4">暂无偏好数据</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add src/components/report/QuizStatsMetrics.jsx src/components/report/PathProgressCard.jsx src/components/report/ModalityPreferenceCard.jsx
git commit -m "feat(report): create stats, progress and modality cards"
```

### Task 4: Create Knowledge Details Cards (1/2)

**Files:**
- Create: `src/components/report/KnowledgeCoordinatesCard.jsx`
- Create: `src/components/report/MasteryBreakdownCard.jsx`

- [ ] **Step 1: Write `KnowledgeCoordinatesCard.jsx`**

```javascript
// src/components/report/KnowledgeCoordinatesCard.jsx
import Icon from '../Icon';

export default function KnowledgeCoordinatesCard({ coordinates }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="grid_view" className="material-symbols-outlined text-cyan-500"/>
        知识坐标 (Knowledge Coordinates)
      </h3>
      <div className="flex flex-wrap gap-2">
        {coordinates?.length > 0 ? (
          coordinates.map((kc, i) => {
            const isMastered = kc.status === 'mastered';
            const isLearning = kc.status === 'learning';
            return (
              <span key={i} className={`px-3 py-1.5 rounded-lg border text-xs font-bold flex items-center gap-1.5 ${
                isMastered ? 'bg-green-50 text-green-700 border-green-100' :
                isLearning ? 'bg-amber-50 text-amber-700 border-amber-100' :
                'bg-slate-100 text-slate-400 border-slate-200'
              }`}>
                <Icon name={isMastered ? 'check_circle' : isLearning ? 'sync' : 'help'} className="material-symbols-outlined text-sm" style={{ fontVariationSettings: '"FILL" 1' }}/>
                {kc.name}
              </span>
            );
          })
        ) : (
          <p className="text-xs text-outline italic text-center py-4">暂无知识坐标数据</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `MasteryBreakdownCard.jsx`**

```javascript
// src/components/report/MasteryBreakdownCard.jsx
import Icon from '../Icon';

export default function MasteryBreakdownCard({ breakdown }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="assessment" className="material-symbols-outlined text-primary text-xl"/>
        练习掌握度 (Mastery Breakdown)
      </h3>
      {breakdown?.length > 0 ? (
        <div className="space-y-3">
          {breakdown.map((item, i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="font-medium text-on-surface">{item.knowledge_point}</span>
                <span className="font-bold text-primary">{item.accuracy}%</span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${item.accuracy}%` }}></div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-outline italic text-center py-4">暂无练习数据</p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/report/KnowledgeCoordinatesCard.jsx src/components/report/MasteryBreakdownCard.jsx
git commit -m "feat(report): create knowledge coordinates and mastery breakdown cards"
```

### Task 5: Create Knowledge Details Cards (2/2)

**Files:**
- Create: `src/components/report/WeakPointsCard.jsx`
- Create: `src/components/report/RecentActivityCard.jsx`

- [ ] **Step 1: Write `WeakPointsCard.jsx`**

```javascript
// src/components/report/WeakPointsCard.jsx
import Icon from '../Icon';

export default function WeakPointsCard({ weakPoints, summary }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-6 flex flex-col justify-between">
      <div>
        <h3 className="text-base font-bold text-on-surface mb-2 flex items-center gap-2">
          <Icon name="local_fire_department" className="material-symbols-outlined text-orange-500"/>
          薄弱知识点 (Weak Points)
        </h3>
        <div className="flex flex-wrap gap-2 mt-3">
          {weakPoints?.length > 0 ? (
            weakPoints.map((wp, i) => (
              <div key={i} className="px-3 py-2 bg-orange-50 rounded-lg border border-orange-100 text-xs">
                <span className="font-bold text-orange-700">{wp.knowledge_point}</span>
                <span className="text-orange-500 ml-2">
                  {wp.error_count}/{wp.total_attempts} 错 ({Math.round(wp.error_rate * 100)}%)
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-outline italic">暂无薄弱点</p>
          )}
        </div>
      </div>

      <div className="pt-4 border-t border-slate-50 grid grid-cols-2 gap-4">
        <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
          <span className="text-xl font-bold text-green-600 block">{summary?.knowledge_mastered || 0}</span>
          <span className="text-[10px] text-secondary">已掌握知识点</span>
        </div>
        <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
          <span className="text-xl font-bold text-orange-600 block">{summary?.knowledge_weak || 0}</span>
          <span className="text-[10px] text-secondary">薄弱知识点数</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `RecentActivityCard.jsx`**

```javascript
// src/components/report/RecentActivityCard.jsx
import Icon from '../Icon';

export default function RecentActivityCard({ activity }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="timeline" className="material-symbols-outlined text-primary text-xl"/>
        最近学习活动 (Recent Activity)
      </h3>
      <div className="space-y-4 max-h-[220px] overflow-y-auto pr-2 scrollbar-thin">
        {activity?.length > 0 ? (
          activity.map((ra, i) => (
            <div key={i} className="flex items-center gap-3 pb-3 border-b border-slate-50 last:border-0">
              <div className="w-8 h-8 rounded-full bg-cyan-100 flex items-center justify-center flex-shrink-0">
                <Icon name="exercise" className="material-symbols-outlined text-cyan-600 text-sm"/>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-on-surface truncate">{ra.chapter || '练习'}</p>
                <p className="text-[10px] text-outline">
                  {ra.created_at ? new Date(ra.created_at).toLocaleDateString('zh-CN') : ''}
                </p>
              </div>
              <div className="text-right flex-shrink-0">
                <span className="text-sm font-bold text-primary">{Math.round(ra.score)}%</span>
                <p className="text-[10px] text-outline">{ra.correct_count}/{ra.total_count} 正确</p>
              </div>
            </div>
          ))
        ) : (
          <p className="text-xs text-outline italic text-center py-8">暂无近期活动</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/report/WeakPointsCard.jsx src/components/report/RecentActivityCard.jsx
git commit -m "feat(report): create weak points and recent activity cards"
```

### Task 6: Refactor Container Component

**Files:**
- Modify: `src/pages/TeacherStudentReport.jsx`

- [ ] **Step 1: Replace container implementation**

```javascript
// Overwrite src/pages/TeacherStudentReport.jsx completely with this:
import { useNavigate, useLocation } from 'react-router-dom';
import { useCourse } from '../context/CourseContext';
import { useAuth } from '../context/AuthContext';
import useStudentReport from '../hooks/useStudentReport';
import FeedbackStatus from '../components/FeedbackStatus';
import Icon from '../components/Icon';

import ReportHeader from '../components/report/ReportHeader';
import ProfileBanner from '../components/report/ProfileBanner';
import QuizStatsMetrics from '../components/report/QuizStatsMetrics';
import PathProgressCard from '../components/report/PathProgressCard';
import ModalityPreferenceCard from '../components/report/ModalityPreferenceCard';
import KnowledgeCoordinatesCard from '../components/report/KnowledgeCoordinatesCard';
import MasteryBreakdownCard from '../components/report/MasteryBreakdownCard';
import WeakPointsCard from '../components/report/WeakPointsCard';
import RecentActivityCard from '../components/report/RecentActivityCard';

export default function TeacherStudentReport() {
  const navigate = useNavigate();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const classId = queryParams.get('course_id');
  const studentId = queryParams.get('student_id');
  const { courses } = useCourse();
  const { user } = useAuth();
  
  const courseName = courses.find(c => c.id === classId)?.name || '学生报告';
  const { reportData: report, isLoading, error } = useStudentReport(classId, studentId);

  if (!classId || !studentId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="error" title="参数缺失" description="请从学生列表页面进入" />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="loading" title="加载报告数据..." />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="error" title="未找到报告数据" description="请检查课程和学生信息是否正确" />
      </div>
    );
  }

  return (
    <div className="text-on-surface bg-background font-body-md antialiased selection:bg-primary-container selection:text-on-primary-container flex flex-col min-h-screen">
      <ReportHeader courseName={courseName} user={user} />

      <main className="flex-1 pt-20 px-gutter pb-xl overflow-y-auto">
        <div className="max-w-[1280px] mx-auto py-margin">
          
          <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-slate-400 text-sm mb-1 cursor-pointer hover:text-primary transition-colors" onClick={() => navigate('/teacher')}>
                <Icon name="chevron_right" className="material-symbols-outlined text-xs transform rotate-180"/>
                <span>返回学生列表</span>
              </div>
              <h1 className="font-h1 text-h1 text-on-background">学情详尽报告 <span className="text-primary-container">· {report.student?.real_name || report.student?.student_id || '学生报告'}</span></h1>
            </div>
            <div className="flex gap-3">
              <button disabled className="flex items-center px-4 py-2 bg-slate-100 border border-outline-variant rounded-xl font-label-sm text-label-sm text-slate-400 cursor-not-allowed opacity-60">
                <Icon name="print" className="material-symbols-outlined mr-2"/> 导出报告 (暂不可用)
              </button>
              <button disabled className="flex items-center px-4 py-2 bg-slate-200 text-slate-400 rounded-xl font-label-sm text-label-sm font-bold cursor-not-allowed opacity-60">
                <Icon name="send" className="material-symbols-outlined mr-2"/> 发送反馈 (暂不可用)
              </button>
            </div>
          </div>

          <div className="space-y-8">
            <ProfileBanner report={report} classId={classId} />

            {report.evaluation_summary?.summary_text && (
              <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-100">
                <p className="text-xs text-slate-500 font-bold uppercase mb-1">AI 分析</p>
                <p className="text-sm text-slate-600 leading-relaxed">{report.evaluation_summary.summary_text}</p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <QuizStatsMetrics stats={report.quiz_stats} />
              <PathProgressCard progress={report.path_progress} />
              <ModalityPreferenceCard preferences={report.profile_summary?.modal_preference} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              <KnowledgeCoordinatesCard coordinates={report.profile_summary?.knowledge_coordinates} />
              <MasteryBreakdownCard breakdown={report.quiz_stats?.mastery_breakdown} />
              <WeakPointsCard weakPoints={report.weak_points} summary={report.profile_summary} />
              <RecentActivityCard activity={report.recent_activity} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Build and Test**

Run: `npm run lint && npm run build`
Expected: Succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add src/pages/TeacherStudentReport.jsx
git commit -m "refactor(report): integrate custom hooks and presentational components in TeacherStudentReport"
```
