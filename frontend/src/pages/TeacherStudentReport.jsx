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
  const { user, logout } = useAuth();
  
  const courseName = courses.find(c => c.id === classId)?.name || '学生报告';
  const { reportData: report, isLoading, error } = useStudentReport(classId, studentId);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

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
      <ReportHeader courseName={courseName} user={user} onLogout={handleLogout} />

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
