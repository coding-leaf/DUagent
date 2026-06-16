import { useState, useEffect } from 'react';
import { learningService } from '../../api/services/learning';
import { personalizedResourcesService } from '../../api/services/personalizedResources';
import { useCourse } from '../../context/CourseContext';
import Icon from '../Icon';

const QUESTION_TYPE_OPTIONS = [
  { value: 'single_choice', label: '单选题', icon: 'radio_button_checked' },
  { value: 'multi_choice', label: '多选题', icon: 'check_box' },
  { value: 'short_answer', label: '问答题', icon: 'edit_note' },
];

const RESOURCE_TYPE_OPTIONS = [
  { value: 'document', label: '文档', icon: 'description' },
  { value: 'mindmap', label: '思维导图', icon: 'account_tree' },
  { value: 'reading', label: '阅读材料', icon: 'menu_book' },
  { value: 'code', label: '代码示例', icon: 'code' },
];

export default function GenerateModal({ courseId, onClose, onGenerated }) {
  const { activeCourseId } = useCourse();
  const cid = courseId || activeCourseId;

  const [step, setStep] = useState(1);
  const [nodes, setNodes] = useState([]);
  const [loadingPath, setLoadingPath] = useState(true);

  const [selectedChapter, setSelectedChapter] = useState(null);
  const [selectedKp, setSelectedKp] = useState(null);
  const [selectedQuestionTypes, setSelectedQuestionTypes] = useState([]);
  const [selectedResourceTypes, setSelectedResourceTypes] = useState([]);

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!cid) return;
    learningService.getLearningPath(cid).then(res => {
      if (res.code === 200) {
        setNodes(res.data.nodes || []);
      }
    }).catch(() => {}).finally(() => setLoadingPath(false));
  }, [cid]);

  const chapters = [...new Set(nodes.map(n => n.chapter).filter(Boolean))];
  const kpsForChapter = selectedChapter
    ? nodes.filter(n => n.chapter === selectedChapter).map(n => ({ id: n.id, name: n.name }))
    : [];

  const canSubmit = selectedKp && (selectedQuestionTypes.length > 0 || selectedResourceTypes.length > 0);

  const toggleQuestionType = (val) => {
    setSelectedQuestionTypes(prev =>
      prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]
    );
  };

  const toggleResourceType = (val) => {
    setSelectedResourceTypes(prev =>
      prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]
    );
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setGenerating(true);
    setError(null);
    const promises = [];

    if (selectedQuestionTypes.length > 0) {
      promises.push(
        personalizedResourcesService.generate({
          course_id: cid,
          generate_type: 'quiz',
          source_type: 'manual',
          chapter: selectedChapter,
          knowledge_point: selectedKp,
          question_types: selectedQuestionTypes,
          count: 5,
        })
      );
    }

    if (selectedResourceTypes.length > 0) {
      promises.push(
        personalizedResourcesService.generate({
          course_id: cid,
          generate_type: 'resource',
          source_type: 'manual',
          chapter: selectedChapter,
          knowledge_point: selectedKp,
          resource_types: selectedResourceTypes,
        })
      );
    }

    const results = await Promise.allSettled(promises);
    const allFailed = results.every(r => r.status === 'rejected');
    const hasError = results.some(r => r.status === 'rejected');
    if (hasError) {
      setError(allFailed ? '生成请求失败，请重试' : '部分生成请求失败，已提交的任务仍在执行中');
    }
    setGenerating(false);
    if (!allFailed) {
      onGenerated();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-surface-container flex-shrink-0">
          <div className="flex flex-row items-center justify-between">
            <h2 className="font-h3 text-on-surface">生成个性化资源</h2>
            <button onClick={onClose} className="text-secondary hover:text-on-surface transition-colors flex-shrink-0">
              <Icon name="close" className="material-symbols-outlined"/>
            </button>
          </div>
          {/* Step indicator */}
          <div className="flex flex-row items-center gap-2 mt-3">
            {[1, 2, 3].map(s => (
              <div key={s} className="flex flex-row items-center gap-2">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold transition-colors flex-shrink-0 ${
                  s < step ? 'bg-primary-container text-white' :
                  s === step ? 'bg-cyan-600 text-white' :
                  'bg-surface-container text-secondary'
                }`}>
                  {s < step ? <Icon name="check" className="material-symbols-outlined text-[14px]"/> : s}
                </div>
                {s < 3 && <div className={`h-px w-8 flex-shrink-0 ${s < step ? 'bg-primary-container' : 'bg-surface-container-high'}`} />}
              </div>
            ))}
            <span className="text-label-sm text-secondary ml-2 whitespace-nowrap">
              {step === 1 ? '选择章节' : step === 2 ? '选择知识点' : '选择资源类型'}
            </span>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 min-h-[200px] overflow-y-auto flex-1">
          {loadingPath ? (
            <div className="flex items-center justify-center py-10">
              <Icon name="progress_activity" className="material-symbols-outlined animate-spin text-3xl text-primary"/>
            </div>
          ) : step === 1 ? (
            <div>
              <p className="text-body-md text-secondary mb-4">请选择要生成资源的章节：</p>
              {chapters.length === 0 ? (
                <p className="text-secondary text-center py-6">暂无章节数据，请先确认学习路径已加载</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {chapters.map(ch => (
                    <button
                      key={ch}
                      onClick={() => { setSelectedChapter(ch); setSelectedKp(null); setStep(2); }}
                      className="px-4 py-2 rounded-xl border border-outline-variant text-body-md hover:bg-cyan-50 hover:border-cyan-300 hover:text-cyan-700 transition-colors"
                    >
                      {ch}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : step === 2 ? (
            <div>
              <p className="text-body-md text-secondary mb-4">
                章节：<span className="text-on-surface font-medium">{selectedChapter}</span> — 请选择知识点：
              </p>
              <div className="flex flex-wrap gap-2">
                {kpsForChapter.map(kp => (
                  <button
                    key={kp.id}
                    onClick={() => { setSelectedKp(kp.name); setStep(3); }}
                    className={`px-4 py-2 rounded-xl border text-body-md transition-colors ${
                      selectedKp === kp.name
                        ? 'border-cyan-500 bg-cyan-50 text-cyan-700'
                        : 'border-outline-variant hover:bg-cyan-50 hover:border-cyan-300 hover:text-cyan-700'
                    }`}
                  >
                    {kp.name}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <p className="text-body-md text-secondary mb-4">
                知识点：<span className="text-on-surface font-medium">{selectedKp}</span> — 请选择资源类型（可多选）：
              </p>
              <div className="mb-4">
                <p className="text-label-sm text-secondary uppercase tracking-wider mb-2">练习题</p>
                <div className="flex flex-wrap gap-2">
                  {QUESTION_TYPE_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => toggleQuestionType(opt.value)}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-body-md transition-colors ${
                        selectedQuestionTypes.includes(opt.value)
                          ? 'border-primary-container bg-primary-container/10 text-primary-container'
                          : 'border-outline-variant hover:bg-surface-container'
                      }`}
                    >
                      <Icon name={opt.icon} className="material-symbols-outlined text-[16px]"/>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-label-sm text-secondary uppercase tracking-wider mb-2">学习资源</p>
                <div className="flex flex-wrap gap-2">
                  {RESOURCE_TYPE_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => toggleResourceType(opt.value)}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-body-md transition-colors ${
                        selectedResourceTypes.includes(opt.value)
                          ? 'border-primary-container bg-primary-container/10 text-primary-container'
                          : 'border-outline-variant hover:bg-surface-container'
                      }`}
                    >
                      <Icon name={opt.icon} className="material-symbols-outlined text-[16px]"/>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              {error && <p className="text-error text-label-sm mt-3">{error}</p>}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-container flex flex-row items-center justify-between flex-shrink-0 w-full">
          <button
            onClick={() => step > 1 ? setStep(step - 1) : onClose()}
            className="min-w-[80px] px-4 py-2 text-secondary hover:text-on-surface transition-colors font-bold text-center block whitespace-nowrap flex-shrink-0"
            style={{ wordBreak: 'keep-all', whiteSpace: 'nowrap' }}
          >
            {step > 1 ? '上一步' : '取消'}
          </button>
          {step === 3 && (
            <button
              onClick={handleSubmit}
              disabled={!canSubmit || generating}
              className="flex flex-row items-center gap-2 px-5 py-2 bg-primary-container text-white rounded-xl font-bold hover:brightness-110 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap flex-shrink-0"
            >
              {generating ? (
                <Icon name="progress_activity" className="material-symbols-outlined animate-spin text-[16px]"/>
              ) : (
                <Icon name="auto_awesome" className="material-symbols-outlined text-[16px]"/>
              )}
              {generating ? '生成中...' : '确认生成'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
