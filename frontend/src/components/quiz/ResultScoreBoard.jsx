import Icon from '../Icon';

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s < 10 ? '0' : ''}${s}`;
};

export default function ResultScoreBoard({ accuracy, resultData, diagnosisData }) {
  return (
    <div className="grid grid-cols-12 gap-md mb-lg items-stretch">
      {/* Accuracy Score */}
      <div className="col-span-4 bg-surface-container-low p-md rounded-xl flex flex-col items-center justify-center text-center">
        <span className="font-label-sm text-label-sm text-secondary mb-base">正确率</span>
        <div className="relative flex items-center justify-center h-24 w-24">
          <svg className="absolute inset-0 h-24 w-24 transform -rotate-90">
            <circle className="text-surface-container-highest" cx="48" cy="48" fill="transparent" r="40" stroke="currentColor" strokeWidth="8"></circle>
            <circle className="text-primary-container" cx="48" cy="48" fill="transparent" r="40" stroke="currentColor" strokeDasharray="251.2" strokeDashoffset={251.2 - (251.2 * accuracy) / 100} strokeWidth="8"></circle>
          </svg>
          <span className="text-h3 font-h3 text-on-surface">{accuracy}%</span>
        </div>
      </div>
      {/* Time & Rank */}
      <div className="col-span-8 grid grid-cols-2 gap-md">
        <div className="bg-white border border-outline-variant p-md rounded-xl flex items-center gap-md">
          <div className="h-12 w-12 bg-primary-container/10 rounded-full flex items-center justify-center text-primary-container">
            <Icon name="timer" className="material-symbols-outlined"/>
          </div>
          <div>
            <span className="block font-label-sm text-label-sm text-secondary">练习耗时</span>
            <span className="font-h3 text-h3 text-on-surface">{resultData ? formatTime(resultData.time_spent) : '0:00'}</span>
          </div>
        </div>
        {/* Comparison Chart Placeholder */}
        <div className="col-span-2 bg-surface-container-lowest border-2 border-primary-container/20 p-md rounded-2xl relative overflow-hidden h-full flex items-center shadow-sm">
          <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
            <Icon name="psychology" className="material-symbols-outlined text-[80px]"/>
          </div>
          <div className="flex gap-md w-full">
            <div className="flex-shrink-0 h-12 w-12 rounded-xl bg-primary-container flex items-center justify-center text-white shadow-lg">
              <Icon name="smart_toy" className="material-symbols-outlined"/>
            </div>
            <div className="flex-1 overflow-y-auto max-h-[120px] custom-scrollbar pr-2">
              <h4 className="font-body-lg font-bold text-on-surface mb-1">AI 智能教练建议</h4>
              <div className="font-body-md text-on-surface-variant leading-relaxed text-sm space-y-1">
                {diagnosisData ? (
                  <>
                    <p className="text-primary-container font-medium">{diagnosisData.summary}</p>
                    {diagnosisData.suggestions && diagnosisData.suggestions.length > 0 && (
                      <ul className="list-disc list-inside pl-1 text-on-surface">
                        {diagnosisData.suggestions.map((sug, idx) => (
                          <li key={idx} className="break-words whitespace-normal">{sug}</li>
                        ))}
                      </ul>
                    )}
                  </>
                ) : (
                  <p>
                    {accuracy >= 80 ? (
                      <>总体表现优异！你在<span className="text-primary font-bold">基础知识点</span>上非常熟练。继续保持！</>
                    ) : (
                      <>表现一般，部分知识点仍需加强。建议针对错题进行强化训练。</>
                    )}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
