import Icon from '../Icon';

export default function LearningDirectionCard({
  drive_intent,
  handleGoalChange,
  goalSubmitting,
  customInstruction,
  setCustomInstruction,
  handleInstructionSubmit,
  instructionSubmitting,
  instructionError,
  instructionSuccess
}) {
  return (
    <section className="lg:col-span-5 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex flex-col gap-6">
      {/* 学习方向 */}
      <div>
        <h3 className="font-h3 text-xl mb-2 flex items-center gap-2 text-on-surface">
          <Icon name="flag" className="material-symbols-outlined text-cyan-500"/> 当前学习方向
        </h3>
        <p className="text-sm text-secondary mb-4">选择你学这门课的主要目的，影响 AI 辅导策略。</p>
        <div className="flex gap-3">
          {[
            { key: 'exam_sprint', label: '备考冲刺', icon: 'school' },
            { key: 'daily_homework', label: '课后巩固', icon: 'menu_book' },
            { key: 'casual', label: '兴趣拓展', icon: 'lightbulb' },
          ].map(({ key, label, icon }) => {
            const active = drive_intent?.type === key;
            return (
              <button
                key={key}
                onClick={() => handleGoalChange(key)}
                disabled={goalSubmitting}
                className={`flex-1 flex flex-col items-center gap-1.5 py-3 px-2 rounded-xl border text-sm font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                  active
                    ? 'border-cyan-500 bg-cyan-50 text-cyan-700'
                    : 'border-slate-200 bg-slate-50 text-slate-500 hover:border-cyan-300 hover:bg-cyan-50/50'
                }`}
              >
                <Icon name={icon} className="material-symbols-outlined text-xl"/>
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 个性化偏好 */}
      <div>
        <h3 className="font-h3 text-xl mb-2 flex items-center gap-2 text-on-surface">
          <Icon name="tune" className="material-symbols-outlined text-cyan-500"/> 个性化偏好
        </h3>
        <p className="text-sm text-secondary mb-3">
          告诉 AI 你希望它怎么跟你说话，每次对话都会遵循这个偏好。
        </p>
        <textarea
          value={customInstruction}
          onChange={(e) => setCustomInstruction(e.target.value)}
          maxLength={500}
          rows={4}
          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-on-surface outline-none focus:border-cyan-400 focus:bg-white transition-colors resize-none"
          placeholder="例如：回答要简洁，多用代码举例，不要长篇大论。遇到我不懂的概念先打比方再讲原理。"
        />
        <div className="flex items-center justify-between mt-2">
          <span className={`text-xs ${instructionError ? 'text-red-500' : instructionSuccess ? 'text-green-600' : 'text-slate-400'}`}>
            {instructionError || (instructionSuccess ? '已保存' : `${customInstruction?.length || 0}/500`)}
          </span>
          <button
            onClick={handleInstructionSubmit}
            disabled={instructionSubmitting}
            className="px-4 py-2 rounded-xl bg-cyan-600 text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-700 transition-colors"
          >
            {instructionSubmitting ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </section>
  );
}
