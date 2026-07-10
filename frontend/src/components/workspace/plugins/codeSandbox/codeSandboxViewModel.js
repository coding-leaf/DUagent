export const isExecutionFailure = (result) => {
  return Boolean(result && result.status && !['success', 'degraded'].includes(result.status));
};

export const getResultBadge = (result) => {
  if (result.status === 'accepted') {
    return {
      className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      label: '全部通过',
    };
  }
  if (result.status === 'wrong_answer') {
    return {
      className: 'bg-rose-50 text-rose-700 border-rose-200',
      label: '用例未通过',
    };
  }
  if (result.status === 'degraded') {
    return {
      className: 'bg-amber-50 text-amber-700 border-amber-200',
      label: '容错分析模式',
    };
  }
  if (result.compile_status === 'Compilation Error') {
    return {
      className: 'bg-rose-50 text-rose-700 border-rose-200',
      label: '编译失败',
    };
  }
  if (isExecutionFailure(result)) {
    return {
      className: 'bg-rose-50 text-rose-700 border-rose-200',
      label: '运行失败',
    };
  }
  return {
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    label: '运行完毕',
  };
};

export const getRunToastMessage = (result) => {
  if (result.status === 'degraded') {
    return '评测机不可用，已启用静态分析容错';
  }
  if (result.compile_status === 'Compilation Error') {
    return '编译失败，请检查语法错误';
  }
  if (isExecutionFailure(result)) {
    return '程序运行失败，请查看终端输出';
  }
  return '代码运行完成';
};

export const getSourceFilename = (language) => {
  if (language === 'c') return 'main.c';
  if (language === 'cpp') return 'main.cpp';
  if (language === 'python') return 'main.py';
  if (language === 'java') return 'Main.java';
  if (language === 'go') return 'main.go';
  if (language === 'javascript') return 'main.js';
  return `main.${language || 'txt'}`;
};

export const buildAskAIPrompt = ({ code, language, stdin, result }) => {
  let debugDetails = '';
  if (result) {
    if (result.status === 'degraded') {
      debugDetails = `【评测环境状态】：沙箱暂时不可用 (原因: ${result.message})\n`;
    } else if (result.compile_status === 'Compilation Error') {
      debugDetails = `【编译错误信息】：\n${result.compile_output}\n`;
    } else if (result.execution) {
      debugDetails = `【标准输出 (stdout)】：\n${result.execution.stdout}\n`;
      if (result.execution.stderr) {
        debugDetails += `【标准错误 (stderr)】：\n${result.execution.stderr}\n`;
      }
      debugDetails += `【程序退出状态】：Exit Code ${result.execution.exit_code}\n`;
    }
  }

  return `我正在练习当前编程调试题，以下是我的当前代码与运行状态：

【代码内容】：
\`\`\`${language}
${code}
\`\`\`

【标准输入 (stdin)】：
${stdin}

${debugDetails}
请帮我指出我代码中的逻辑漏洞或编译问题，并指导我如何进行修复。`;
};
