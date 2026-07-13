import Icon from '../Icon';

const STATUS_META = {
  running: {
    label: '进行中',
    icon: null,
    shell: 'border-cyan-200 bg-cyan-50/60 text-cyan-800',
    dot: 'border-cyan-200 border-t-cyan-600 animate-spin'
  },
  completed: {
    label: '完成',
    icon: 'check_circle',
    shell: 'border-emerald-200 bg-emerald-50/50 text-emerald-800',
  },
  success: {
    label: '完成',
    icon: 'check_circle',
    shell: 'border-emerald-200 bg-emerald-50/50 text-emerald-800',
  },
  neutral: {
    label: '无结果',
    icon: 'info',
    shell: 'border-slate-200 bg-slate-50/70 text-slate-700',
  },
  warning: {
    label: '降级',
    icon: 'warning_amber',
    shell: 'border-amber-200 bg-amber-50/70 text-amber-800',
  },
  error: {
    label: '失败',
    icon: 'error_outline',
    shell: 'border-red-200 bg-red-50/60 text-red-700',
  }
};

const TOOL_TITLE_MAP = {
  reset_tools: '整理工具状态',
  TaskCreate: '创建计划任务',
  TaskUpdate: '更新计划任务',
  TaskList: '查看计划任务',
  TaskGet: '读取计划任务',
  draft_study_artifact: '生成学习资料',
  read_learning_state: '读取学习状态',
  review_grounding: '检查回答依据',
  write_artifact_file: '编写工作区课件',
  create_code_sandbox_card: '装载代码实操沙箱',
  run_code_in_oj: '在线沙盒编译运行',
  retrieve_course_context: '检索教材教学上下文',
  read_learning_progress: '分析学情薄弱点',
  read_recent_answers: '调取历史作答轨迹',
  validate_personal_code_problem_draft: '编程练习题 OJ 校验',
  publish_personal_code_problem: '发布私有编程练习',
  publish_personal_choice_quiz: '发布私有选择题练习',
  resume_personal_practice_delivery: '恢复互动练习发布',
  create_personalized_resource_draft: '生成个性化教学草稿',
  record_personalized_validation: '对齐性格式检验',
  review_personalized_resource: '教学合规性审核',
  publish_personalized_resource: '发布个性化学习资源'
};

export default function ToolCallCard({ name, title, status, description, inputSummary, outputSummary }) {
  const isRunning = status === 'running';
  const meta = STATUS_META[status] || STATUS_META.running;
  const mappedTitle = TOOL_TITLE_MAP[name];
  const displayTitle = title || mappedTitle || name || '工具调用';
  const shouldShowRawName = name && !mappedTitle && name !== displayTitle;

  return (
    <div className={`rounded-lg border p-3 text-[11px] shadow-sm ${meta.shell}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {isRunning ? (
              <span className={`inline-block w-3.5 h-3.5 rounded-full border-2 ${meta.dot}`} />
            ) : (
              <Icon name={meta.icon} className="text-[15px] flex-shrink-0" />
            )}
            <span className="font-semibold text-slate-800 truncate text-[12px]">{displayTitle}</span>
          </div>
          {shouldShowRawName && (
            <div className="mt-1 font-mono text-[9px] text-slate-500 truncate">{name}</div>
          )}
        </div>
        <span className="rounded-full bg-white/80 px-2 py-0.5 text-[9px] font-bold text-slate-500 border border-white/80 flex-shrink-0">
          {meta.label}
        </span>
      </div>

      {description && (
        <p className="mt-2 leading-relaxed text-slate-600">{description}</p>
      )}
      {inputSummary && (
        <p className="mt-2 rounded-lg bg-white/70 px-2.5 py-1.5 leading-relaxed text-slate-500">
          输入：{inputSummary}
        </p>
      )}
      {outputSummary && (
        <p className="mt-2 rounded-lg bg-white/80 px-2.5 py-1.5 leading-relaxed text-slate-700">
          结果：{outputSummary}
        </p>
      )}
    </div>
  );
}
