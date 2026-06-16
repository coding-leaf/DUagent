import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import { useCourse } from '../context/CourseContext';
import { personalizedResourcesService } from '../api/services/personalizedResources';
import GenerateModal from '../components/personalized/GenerateModal';
import Icon from '../components/Icon';

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

// 按知识点分组题目，返回 [{ knowledge_point, items[] }]
function groupQuestionsByKp(items) {
  const map = new Map();
  for (const item of items) {
    if (!item.question) continue;
    const kp = item.question.knowledge_point || '未分类';
    if (!map.has(kp)) map.set(kp, []);
    map.get(kp).push(item);
  }
  return Array.from(map.entries()).map(([kp, kpItems]) => ({ knowledge_point: kp, items: kpItems }));
}

function QuizGroupCard({ kp, kpItems, courseId, navigate, onDelete }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  
  const count = kpItems.length;
  // 仅筛选出有效的题目的 items
  const validQuestionItems = kpItems.filter(i => i.question);
  
  const handleToggleSelectAll = (e) => {
    e.stopPropagation();
    if (selectedIds.length === validQuestionItems.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(validQuestionItems.map(i => i.question.id));
    }
  };

  const handleToggleItem = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleStartPractice = (e) => {
    e.stopPropagation();
    if (selectedIds.length === 0) {
      // 未勾选任何题目：维持原有逻辑
      navigate(`/quiz?course_id=${courseId}&source=personalized&knowledge_point=${encodeURIComponent(kp)}`);
    } else {
      // 勾选了具体题目
      navigate(`/quiz?course_id=${courseId}&knowledge_point=${encodeURIComponent(kp)}&question_ids=${selectedIds.join(',')}`);
    }
  };

  return (
    <div className="bg-white border border-outline-variant rounded-xl overflow-hidden hover:shadow-sm transition-shadow">
      {/* Header */}
      <div 
        className="p-4 flex items-center justify-between gap-4 bg-slate-50 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-full bg-primary-container/10 flex items-center justify-center text-primary-container flex-shrink-0">
            <Icon name="quiz" className="material-symbols-outlined"/>
          </div>
          <div className="min-w-0">
            <h3 className="text-body-md font-bold text-slate-800">{kp}</h3>
            <p className="text-label-sm text-slate-500 mt-1">共 {count} 道个性化题目</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button
            onClick={handleStartPractice}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-container text-white rounded-xl text-label-sm font-bold hover:brightness-110 active:scale-95 transition-all"
          >
            <Icon name="play_arrow" className="material-symbols-outlined text-[16px]"/>
            开始练习 {selectedIds.length > 0 ? `(已选 ${selectedIds.length})` : ''}
          </button>
          <Icon name={isExpanded ? 'expand_less' : 'expand_more'} className="material-symbols-outlined text-slate-400"/>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && validQuestionItems.length > 0 && (
        <div className="border-t border-slate-200">
          {/* Toolbar */}
          <div className="px-4 py-2 bg-slate-100 border-b border-slate-200 flex justify-between items-center text-xs">
            <label className="flex items-center gap-2 cursor-pointer text-slate-700 font-medium hover:text-primary">
              <input 
                type="checkbox" 
                className="rounded border-slate-300 text-primary focus:ring-primary cursor-pointer w-4 h-4"
                checked={selectedIds.length === validQuestionItems.length && validQuestionItems.length > 0}
                onChange={handleToggleSelectAll}
              />
              全选本知识点下的 {validQuestionItems.length} 题
            </label>
            <span className="text-slate-500">按最近生成时间排列</span>
          </div>

          {/* Scrollable List */}
          <div className="max-h-[320px] overflow-y-auto">
            {validQuestionItems.map((item) => {
              const q = item.question;
              const isSelected = selectedIds.includes(q.id);
              // 截断内容作为摘要
              const summary = q.content.length > 50 ? q.content.substring(0, 50) + '...' : q.content;
              const diffLabel = { easy: '简单', medium: '中等', hard: '困难' }[q.difficulty] || q.difficulty;
              const sourceLabel = SOURCE_LABEL[item.source_type] || item.source_type;

              return (
                <div 
                  key={q.id} 
                  className={`p-3 border-b border-slate-100 flex items-start gap-3 transition-colors ${isSelected ? 'bg-sky-50/50' : 'hover:bg-slate-50'}`}
                >
                  <input 
                    type="checkbox" 
                    className="mt-1 rounded border-slate-300 text-primary focus:ring-primary cursor-pointer w-4 h-4"
                    checked={isSelected}
                    onChange={() => handleToggleItem(q.id)}
                  />
                  <div className="flex-1 min-w-0" onClick={() => handleToggleItem(q.id)} style={{ cursor: 'pointer' }}>
                    <div className="flex gap-2 items-center mb-1">
                      <span className="text-[10px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded">{sourceLabel}</span>
                      <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">难度: {diffLabel}</span>
                    </div>
                    <p className="text-sm font-medium text-slate-800 break-words">{summary}</p>
                  </div>
                  <button 
                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                    onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
                    title="删除"
                  >
                    <Icon name="delete" className="material-symbols-outlined text-[18px]"/>
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function ResourceCard({ item, onDelete }) {
  if (item.task_status === 'processing') {
    return (
      <div className="bg-white border border-dashed border-cyan-300 rounded-xl p-md flex items-center gap-md animate-pulse">
        <div className="w-10 h-10 rounded-full bg-cyan-100 flex items-center justify-center">
          <Icon name="progress_activity" className="material-symbols-outlined text-cyan-400 animate-spin"/>
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
      <div className="bg-white border border-error/20 rounded-xl p-md flex justify-between items-center gap-md">
        <div className="flex items-center gap-md">
          <div className="w-10 h-10 rounded-full bg-error-container flex items-center justify-center text-error">
            <Icon name="error" className="material-symbols-outlined"/>
          </div>
          <div>
            <p className="text-body-md font-medium text-error">生成失败</p>
            <p className="text-label-sm text-gray-400">可重新尝试生成</p>
          </div>
        </div>
        {onDelete && (
          <button 
            className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-all"
            onClick={() => onDelete(item.id)}
            title="删除"
          >
            <Icon name="delete" className="material-symbols-outlined text-[20px]"/>
          </button>
        )}
      </div>
    );
  }

  if (item.resource) {
    const r = item.resource;
    return (
      <div className="relative group">
        <Link to={`/resource/${r.id}`} className="block bg-white border border-outline-variant rounded-xl p-md hover:shadow-sm transition-shadow">
        <div className="flex items-start gap-md">
          <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center text-secondary flex-shrink-0">
            <Icon name={TYPE_ICON[r.type] || 'article'} className="material-symbols-outlined"/>
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
      {onDelete && (
        <button 
          className="absolute top-3 right-3 p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500 hover:bg-red-50 rounded transition-all"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(item.id); }}
          title="删除"
        >
          <Icon name="delete" className="material-symbols-outlined text-[20px]"/>
        </button>
      )}
    </div>
    );
  }

  return null;
}

export default function PersonalizedResources() {
  const { activeCourseId } = useCourse();
  const location = useLocation();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingCount, setProcessingCount] = useState(0);
  const [filterSource, setFilterSource] = useState('all');
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

  // 初始加载 + filter 切换时重置 loading
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setLoading(true);
    /* eslint-enable react-hooks/set-state-in-effect */
    fetchItems();
  }, [fetchItems]);

  const handleDelete = async (id) => {
    if (!window.confirm('确定要删除这项资源吗？')) return;
    try {
      const res = await personalizedResourcesService.delete(id);
      if (res.code === 200) {
        fetchItems();
      }
    } catch (e) {
      console.error('Failed to delete', e);
      alert('删除失败，请稍后重试');
    }
  };

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
              <Icon name="add" className="material-symbols-outlined"/>
              生成资源
            </button>
          </div>

          {/* 生成中提示横幅 */}
          {showNewTaskBanner && (
            <div className="mb-4 bg-cyan-50 border border-cyan-200 rounded-xl px-4 py-3 flex items-center gap-3">
              <Icon name="progress_activity" className="material-symbols-outlined text-cyan-500 animate-spin"/>
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
              <Icon name="progress_activity" className="material-symbols-outlined animate-spin text-4xl text-primary"/>
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-20 text-secondary">
              <Icon name="psychology" className="material-symbols-outlined text-6xl mb-4 block text-gray-300"/>
              <p className="text-body-lg">暂无个性化资源</p>
              <p className="text-body-md mt-2">完成练习后正确率低于 60% 会自动触发生成，或点击"生成资源"手动创建</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 生成中/失败的任务卡片 */}
              {items.filter(i => !i.question && !i.resource).length > 0 && (
                <div className="space-y-3">
                  {items.filter(i => !i.question && !i.resource).map(item => (
                    <ResourceCard key={item.id} item={item} onDelete={handleDelete} />
                  ))}
                </div>
              )}

              {/* 练习题：按知识点分组，每组一个"开始练习"入口 */}
              {groupQuestionsByKp(items).length > 0 && (
                <div>
                  <h3 className="text-label-sm text-secondary uppercase tracking-wider mb-3">个性化练习题</h3>
                  <div className="space-y-3">
                    {groupQuestionsByKp(items).map(({ knowledge_point: kp, items: kpItems }) => (
                      <QuizGroupCard
                        key={kp}
                        kp={kp}
                        kpItems={kpItems}
                        courseId={activeCourseId}
                        navigate={navigate}
                        onDelete={handleDelete}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* 学习资源卡片 */}
              {items.filter(i => i.resource).length > 0 && (
                <div>
                  <h3 className="text-label-sm text-secondary uppercase tracking-wider mb-3">个性化学习资源</h3>
                  <div className="space-y-3">
                    {items.filter(i => i.resource).map(item => (
                      <ResourceCard key={item.id} item={item} onDelete={handleDelete} />
                    ))}
                  </div>
                </div>
              )}
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
