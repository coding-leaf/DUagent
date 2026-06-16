import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import { useCourse } from '../context/CourseContext';
import { personalizedResourcesService } from '../api/services/personalizedResources';
import GenerateModal from '../components/personalized/GenerateModal';

const TYPE_ICON = {
  document: 'description',
  mindmap: 'account_tree',
  reading: 'menu_book',
  code: 'code',
  video: 'play_circle',
  single_choice: 'radio_button_checked',
  multi_choice: 'check_box',
  short_answer: 'edit_note',
};

const SOURCE_LABEL = {
  quiz_wrong_answer: '错题触发',
  manual: '手动生成',
};

function ResourceCard({ item }) {
  if (item.task_status === 'processing') {
    return (
      <div className="bg-white border border-dashed border-cyan-300 rounded-xl p-md flex items-center gap-md animate-pulse">
        <div className="w-10 h-10 rounded-full bg-cyan-100 flex items-center justify-center">
          <span className="material-symbols-outlined text-cyan-400 animate-spin">progress_activity</span>
        </div>
        <div>
          <p className="text-body-md font-medium text-secondary">正在生成中...</p>
          <p className="text-label-sm text-gray-400">{SOURCE_LABEL[item.source_type] || item.source_type}</p>
        </div>
      </div>
    );
  }

  if (item.task_status === 'failed') {
    return (
      <div className="bg-white border border-error/20 rounded-xl p-md flex items-center gap-md">
        <div className="w-10 h-10 rounded-full bg-error-container flex items-center justify-center text-error">
          <span className="material-symbols-outlined">error</span>
        </div>
        <div>
          <p className="text-body-md font-medium text-error">生成失败</p>
          <p className="text-label-sm text-gray-400">可重新尝试生成</p>
        </div>
      </div>
    );
  }

  if (item.question) {
    const q = item.question;
    return (
      <div className="bg-white border border-outline-variant rounded-xl p-md hover:shadow-sm transition-shadow">
        <div className="flex items-start gap-md">
          <div className="w-10 h-10 rounded-full bg-primary-container/10 flex items-center justify-center text-primary-container flex-shrink-0">
            <span className="material-symbols-outlined">{TYPE_ICON[q.type] || 'quiz'}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-sm mb-xs flex-wrap">
              <span className="text-label-sm text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded-full">{q.knowledge_point}</span>
              <span className="text-label-sm text-gray-400">{q.difficulty}</span>
              <span className="text-label-sm text-orange-500 bg-orange-50 px-2 py-0.5 rounded-full">{SOURCE_LABEL[item.source_type]}</span>
            </div>
            <p className="text-body-md text-on-surface line-clamp-2">{q.content}</p>
          </div>
        </div>
      </div>
    );
  }

  if (item.resource) {
    const r = item.resource;
    return (
      <Link to={`/resource/${r.id}`} className="block bg-white border border-outline-variant rounded-xl p-md hover:shadow-sm transition-shadow">
        <div className="flex items-start gap-md">
          <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center text-secondary flex-shrink-0">
            <span className="material-symbols-outlined">{TYPE_ICON[r.type] || 'article'}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-sm mb-xs flex-wrap">
              <span className="text-label-sm text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded-full">{r.knowledge_point}</span>
              <span className="text-label-sm text-orange-500 bg-orange-50 px-2 py-0.5 rounded-full">{SOURCE_LABEL[item.source_type]}</span>
            </div>
            <h4 className="text-body-md font-medium text-on-surface truncate">{r.title}</h4>
            {r.description && <p className="text-label-sm text-secondary mt-1 line-clamp-1">{r.description}</p>}
          </div>
        </div>
      </Link>
    );
  }

  return null;
}

export default function PersonalizedResources() {
  const { activeCourseId } = useCourse();
  const location = useLocation();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingCount, setProcessingCount] = useState(0);  const [filterSource, setFilterSource] = useState('all');
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [total, setTotal] = useState(0);
  const pollRef = useRef(null);

  const fetchItems = useCallback(async () => {
    if (!activeCourseId) return;
    try {
      const params = {};
      if (filterSource !== 'all') params.source_type = filterSource;
      const res = await personalizedResourcesService.list(activeCourseId, params);
      if (res.code === 200) {
        setItems(res.data.items);
        setTotal(res.data.total);
        setProcessingCount(res.data.processing_count);
      }
    } catch (e) {
      console.error('Failed to fetch personalized resources', e);
    } finally {
      setLoading(false);
    }
  }, [activeCourseId, filterSource]);

  // 初始加载
  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchItems();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchItems]);

  // 轮询：processingCount > 0 时每 3 秒刷新一次
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (processingCount > 0) {
      pollRef.current = setInterval(fetchItems, 3000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [processingCount, fetchItems]);

  const newTaskId = location.state?.newTaskId;
  const showNewTaskBanner = newTaskId && processingCount > 0;

  return (
    <div className="bg-surface min-h-screen">
      <Navbar />
      <Sidebar />
      <main className="ml-0 lg:ml-64 pt-16 min-h-screen">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="font-h2 text-h2 text-on-surface">个性化资源</h1>
              <p className="text-body-md text-secondary mt-1">专属于你的学习材料与练习题，共 {total} 项</p>
            </div>
            <button
              onClick={() => setShowGenerateModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary-container text-white rounded-xl font-bold hover:brightness-110 active:scale-95 transition-all shadow-sm"
            >
              <span className="material-symbols-outlined">add</span>
              生成资源
            </button>
          </div>

          {/* 生成中提示横幅 */}
          {showNewTaskBanner && (
            <div className="mb-4 bg-cyan-50 border border-cyan-200 rounded-xl px-4 py-3 flex items-center gap-3">
              <span className="material-symbols-outlined text-cyan-500 animate-spin">progress_activity</span>
              <p className="text-body-md text-cyan-700">正在为你生成个性化练习，请稍候...</p>
            </div>
          )}

          {/* 筛选栏 */}
          <div className="flex gap-2 mb-6 flex-wrap">
            {[
              { value: 'all', label: '全部' },
              { value: 'quiz_wrong_answer', label: '错题触发' },
              { value: 'manual', label: '手动生成' },
            ].map(opt => (
              <button
                key={opt.value}
                onClick={() => setFilterSource(opt.value)}
                className={`px-3 py-1.5 rounded-full text-label-sm font-medium transition-colors ${
                  filterSource === opt.value
                    ? 'bg-primary-container text-white'
                    : 'bg-surface-container text-secondary hover:bg-surface-container-high'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* 内容区 */}
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-20 text-secondary">
              <span className="material-symbols-outlined text-6xl mb-4 block text-gray-300">psychology</span>
              <p className="text-body-lg">暂无个性化资源</p>
              <p className="text-body-md mt-2">完成练习后正确率低于 60% 会自动触发生成，或点击"生成资源"手动创建</p>
            </div>
          ) : (
            <div className="space-y-3">
              {items.map(item => (
                <ResourceCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      </main>

      {showGenerateModal && (
        <GenerateModal
          courseId={activeCourseId}
          onClose={() => setShowGenerateModal(false)}
          onGenerated={() => {
            setShowGenerateModal(false);
            fetchItems();
          }}
        />
      )}
    </div>
  );
}
