import Icon from '../Icon';
import { LOADING_TEXTS } from '../../hooks/usePracticeResult';

export default function ResultLoadingState({ currentTextIndex }) {
  return (
    <div className="bg-slate-50 min-h-screen flex items-center justify-center p-4">
      <div className="max-w-[448px] w-full bg-white border border-gray-100 rounded-3xl shadow-xl p-8 flex flex-col items-center text-center">
        <div className="relative flex items-center justify-center h-24 w-24 mb-6">
          {/* Outer spinning progress ring */}
          <div className="absolute inset-0 border-4 border-indigo-100 border-t-indigo-500 rounded-full animate-spin"></div>
          {/* Inner pulsing AI robot icon */}
          <Icon name="smart_toy" className="text-indigo-500 text-4xl animate-pulse"/>
        </div>
        <h3 className="text-2xl font-bold text-gray-800 mb-2 whitespace-nowrap">智能教练评估中</h3>
        <p className="text-sm font-medium text-gray-500 min-h-[24px]">
          {LOADING_TEXTS[currentTextIndex]}
        </p>
      </div>
    </div>
  );
}
