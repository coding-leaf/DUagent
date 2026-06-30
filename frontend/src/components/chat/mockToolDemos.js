export const MOCK_TOOL_DEMOS = {
  weak_plan: {
    prompt: '帮我根据当前薄弱点生成补弱学习计划。',
    answer: '已根据画像、练习结果和课程知识点生成补弱计划。中间工作区已更新「薄弱点分析」和「今日学习计划」。',
    toolCalls: [
      {
        id: 'mock-weak-points',
        name: 'get_weak_points',
        title: '分析薄弱点',
        status: 'completed',
        description: '读取画像、最近练习结果和学习效果快照。',
        inputSummary: '课程上下文 + 最近错题 + 节点掌握度',
        outputSummary: '识别到二叉树遍历、递归实现、AVL 平衡调整 3 个重点薄弱点'
      },
      {
        id: 'mock-plan',
        name: 'draft_learning_plan',
        title: '生成学习计划',
        status: 'completed',
        description: '按补弱优先策略拆分今日学习任务。',
        outputSummary: '生成 4 个学习任务，预计 170 分钟'
      }
    ],
    artifacts: [
      {
        type: 'WeakPointsCard',
        props: {
          title: '薄弱点分析',
          points: [
            { name: '二叉树遍历', mastery: 28 },
            { name: '递归实现', mastery: 46 },
            { name: '平衡二叉树 (AVL)', mastery: 58 },
            { name: '图的最短路径', mastery: 72 }
          ]
        }
      },
      {
        type: 'StudyPlanCard',
        props: {
          planDate: '今日',
          tasks: [
            { name: '二叉树遍历重点突破', duration: 60 },
            { name: '递归思想强化训练', duration: 45 },
            { name: 'AVL 旋转过程复盘', duration: 45 },
            { name: '错题回顾与小结', duration: 20 }
          ]
        }
      }
    ]
  },
  resources: {
    prompt: '请根据我的薄弱点推荐一组资源。',
    answer: '已匹配一组与薄弱点相关的资源包，优先覆盖二叉树遍历和递归实现。',
    toolCalls: [
      {
        id: 'mock-resources',
        name: 'get_recommended_resources',
        title: '推荐学习资源',
        status: 'completed',
        description: '根据薄弱点和课程资源库匹配资源。',
        inputSummary: '薄弱点：二叉树遍历、递归实现',
        outputSummary: '推荐 3 个资源，含思维导图、代码示例和练习集'
      }
    ],
    artifacts: [
      {
        type: 'Markdown',
        props: {
          content: '## 推荐资源包\n\n| 资源 | 类型 | 推荐理由 |\n| --- | --- | --- |\n| 递归遍历思维导图 | 思维导图 | 帮助区分前序、中序、后序遍历顺序 |\n| 二叉树遍历代码示例 | 代码 | 对照递归调用栈理解执行过程 |\n| 遍历专项练习集 | 练习 | 用 20 道题巩固薄弱节点 |\n\n建议先看思维导图，再阅读代码示例，最后进入专项练习。'
        }
      }
    ]
  },
  lesson: {
    prompt: '生成一个二叉树遍历的讲解页。',
    answer: '已生成一份二叉树遍历讲解页草稿，可在中间工作区预览。',
    toolCalls: [
      {
        id: 'mock-lesson',
        name: 'draft_html_lesson',
        title: '生成讲解页',
        status: 'completed',
        description: '将知识点拆成讲解结构、步骤和示例。',
        outputSummary: '生成 1 份类 PPT 讲解页草稿'
      }
    ],
    artifacts: [
      {
        type: 'Markdown',
        props: {
          content: '# 二叉树遍历讲解页\n\n### 1. 先记住顺序\n\n- 前序：根 -> 左 -> 右\n- 中序：左 -> 根 -> 右\n- 后序：左 -> 右 -> 根\n\n### 2. 看递归模板\n\n```c\nvoid preorder(Node* root) {\n  if (!root) return;\n  visit(root);\n  preorder(root->left);\n  preorder(root->right);\n}\n```\n\n### 3. 练习建议\n\n先手写访问顺序，再对照递归调用栈。'
        }
      }
    ]
  },
  quiz: {
    prompt: '生成一道二叉树遍历练习预览。',
    answer: '已生成一题练习预览。正式练习仍建议跳转到练习页完成记录。',
    toolCalls: [
      {
        id: 'mock-quiz',
        name: 'draft_quiz_preview',
        title: '生成练习预览',
        status: 'completed',
        description: '根据当前薄弱点生成一道低风险预览题。',
        outputSummary: '生成 1 道选择题'
      }
    ],
    artifacts: [
      {
        type: 'QuizCard',
        props: {
          question: '若对二叉树进行中序遍历，访问顺序的核心规则是什么？',
          choices: ['根 -> 左 -> 右', '左 -> 根 -> 右', '左 -> 右 -> 根', '层序从上到下'],
          correctAnswer: 1
        }
      }
    ]
  }
};
