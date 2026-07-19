import { Link } from 'react-router-dom';

import usePersonalizedResources from '../../../hooks/usePersonalizedResources';
import Icon from '../../Icon';
import ExistingPersonalizedResourceCard from '../../personalized/PersonalizedResourceCard';

export default function PersonalizedResourceCard({ course_id: courseId, task_id: taskId, resources = [] }) {
  const { items } = usePersonalizedResources(taskId ? courseId : null);
  const generated = taskId ? items.find((item) => item.task_id === taskId) : null;

  if (taskId) {
    return generated ? (
      <ExistingPersonalizedResourceCard item={generated} />
    ) : (
      <div className="rounded-xl border border-dashed border-cyan-200 bg-white p-5 text-cyan-800 flex gap-3 items-center">
        <Icon name="progress_activity" className="animate-spin" />
        <span>个性化资源任务正在启动</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {resources.map((resource) => (
        <Link
          key={resource.id}
          to={`/resource/${resource.id}`}
          className="block rounded-xl border border-slate-200 bg-white p-4 hover:border-cyan-300 hover:shadow-sm"
        >
          <div className="flex items-start gap-3">
            <Icon name="auto_awesome" className="text-cyan-700" />
            <div className="min-w-0">
              <h4 className="font-medium text-slate-900">{resource.title}</h4>
              {resource.summary && <p className="mt-1 text-sm text-slate-600">{resource.summary}</p>}
              {resource.reason && <p className="mt-2 text-xs text-cyan-700">推荐理由：{resource.reason}</p>}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
