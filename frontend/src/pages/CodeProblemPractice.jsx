import { useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import CodeSandboxCard from '../components/workspace/plugins/codeSandbox/CodeSandboxCard';

export default function CodeProblemPractice() {
  const { problemId } = useParams();

  return (
    <div className="bg-surface min-h-screen">
      <Navbar />
      <main className="pt-16 min-h-screen">
        <div className="max-w-[896px] mx-auto px-6 py-8">
          <h1 className="font-h2 text-h2 text-on-surface mb-2">个性化编程练习</h1>
          <p className="text-body-md text-secondary mb-6">提交后将使用固定测试用例进行评测。</p>
          <CodeSandboxCard problem_id={problemId} />
        </div>
      </main>
    </div>
  );
}
