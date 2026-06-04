export default function chatMock(mock) {
  // 会话列表
  mock.onGet('/api/v1/chat/sessions').reply(200, {
    code: 200,
    message: 'success',
    data: [
      { session_id: 'sess_9527', title: '二叉搜索树解析', icon: 'account_tree' },
      { session_id: 'sess_9528', title: '红黑树的应用场景', icon: 'library_books' },
      { session_id: 'sess_9529', title: '智能体B-树优化建议', icon: 'smart_toy' },
      { session_id: 'sess_9530', title: '图的最短路径算法', icon: 'share' },
      { session_id: 'sess_9531', title: '动态规划：背包问题', icon: 'calculate' },
      { session_id: 'sess_9532', title: '排序算法时间复杂度', icon: 'bar_chart' }
    ]
  });

  mock.onGet(/\/api\/v1\/chat\/history/).reply(() => {
    return [200, {
      code: 200,
      message: 'success',
      data: {
        session_id: 'sess_9527',
        messages: [
          { 
            id: 'm1', 
            role: 'assistant', 
            content: '你好！我是你的数据结构学习助手。你可以上传代码片段、逻辑图，或者直接描述你的疑惑。目前我特别擅长解析 **动态规划** 与 **树形结构** 的可视化逻辑。', 
            suggestions: ['如何理解AVL树的旋转？', '解释哈希冲突的解决方法'] 
          },
          { 
            id: 'm2', 
            role: 'user', 
            content: '你能帮我分析一下这段二叉搜索树的插入逻辑吗？我总是在递归退栈时处理不好平衡因子。' 
          },
          { 
            id: 'm3', 
            role: 'assistant', 
            content: '当然可以。在处理平衡因子（Balance Factor）时，核心在于 **“自底向上”** 的更新。\n\n当你插入节点 30 时，30 成为 20 的右孩子。回溯时，20 的平衡因子从 0 变为 -1。如果此时绝对值大于 1，则触发旋转。你可以参考以下代码模板：\n\n```cpp\nint getHeight(Node* n) {\n    if (n == NULL) return 0;\n    return n->height;\n}\n\nint getBalance(Node* n) {\n    if (n == NULL) return 0;\n    return getHeight(n->left) - getHeight(n->right);\n}\n```\n\n如果还有问题，可以上传你的 `.cpp` 或 `.java` 文件，我为你进行逐行诊断。',
            has_visual: true
          },
          {
            id: 'm4',
            role: 'user',
            content: '我懂了，那我怎么计算它的最坏时间复杂度呢？能用公式说明吗？'
          },
          {
            id: 'm5',
            role: 'assistant',
            content: '在最坏的情况下，二叉搜索树会退化为一条链表。假设我们有 $n$ 个节点依次插入，且插入的序列是有序的。那么树的高度 $h = n$。\n\n每次插入第 $i$ 个节点时，需要经过 $i-1$ 次比较。总的比较次数 $C$ 可以用以下公式表示：\n\n$C = \\sum_{i=1}^{n} (i-1) = \\frac{n(n-1)}{2}$\n\n因此，最坏情况下的时间复杂度为 $O(n^2)$。这也是为什么我们需要引入 AVL 树或红黑树来维持树的高度为 $O(\\log n)$，从而保证所有基本操作的时间复杂度都是 $O(\\log n)$。\n\n如果你需要进一步了解红黑树的着色与旋转策略，随时告诉我！'
          }
        ]
      }
    }];
  });

  // 发送消息
  mock.onPost('/api/v1/chat/completions').reply((config) => {
    const data = JSON.parse(config.data);
    
    // Simple response generation
    const responseText = `(由代码审查智能体回复)\n关于你的提问：“${data.message}”，我认为你需要结合具体的代码实现去理解。你可以尝试在本地编辑器中调试，或者使用我们的在线沙盒。如果需要进一步的公式推导，可以随时呼叫【算法推导智能体】。`;

    return [200, {
      code: 200,
      message: 'success',
      data: {
        id: 'm' + Date.now(),
        role: 'assistant',
        content: responseText
      }
    }];
  });
}
