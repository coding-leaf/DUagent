# 练题知识点上下文闭环 — 设计 spec

**日期：** 2026-06-16  
**范围：** 纯前端，无新接口，无后端改动  

---

## 目标

每次练题都携带"当前知识点"上下文，答题结束后 PracticeResult 页面根据正确率提供两个清晰操作：
- **再练一遍**（零延迟，直接用现有题目再来一次）
- **生成新一批**（后台异步生成，跳个性化资源页等待）

形成闭环：学习路径练题 → 失败 → 生成个性化题 → 按知识点练 → 再失败 → 再生成。

---

## 改动文件

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/Quiz.jsx` | 提交时在 navigate state 里附带 `quizContext`（node_id / knowledge_point / source） |
| `frontend/src/pages/PracticeResult.jsx` | 读取 quizContext，显示知识点标题，低正确率时显示"再练一遍"+"生成新一批"两个按钮 |

PersonalizedResources.jsx 已经在跳转 quiz 时带了 `source=personalized&knowledge_point=xxx`，Quiz.jsx 读到这两个参数后会带入 state，自动形成闭环，无需额外修改。

---

## 1. Quiz.jsx 改动

### 1.1 提交时附带 quizContext

找到 `navigate('/quiz/result', { state: { result: res.data } })` 这行，改为：

```js
navigate('/quiz/result', {
  state: {
    result: res.data,
    quizContext: {
      node_id: nodeId || null,
      knowledge_point: knowledgePointParam || quizData.questions?.[0]?.knowledge_point || null,
      source: sourceParam || null,
    },
  },
});
```

**逻辑：**
- `node_id`：从 URL `?node_id=xxx` 读，来自学习路径
- `knowledge_point`：优先从 URL `?knowledge_point=xxx` 读（来自个性化资源），fallback 到题目的第一题知识点
- `source`：从 URL `?source=xxx` 读（personalized / 空）

---

## 2. PracticeResult.jsx 改动

### 2.1 读取 quizContext

```js
const quizContext = location.state?.quizContext || null;
const contextKp = quizContext?.knowledge_point || null;
const contextSource = quizContext?.source || null;
const contextNodeId = quizContext?.node_id || null;
```

### 2.2 Modal Header 显示知识点

在 Modal Header 的副标题部分（当前写死的"第4章：树形结构 - 平衡二叉树专项练习"），改为动态显示：

```jsx
<p className="font-body-md text-secondary">
  {contextKp ? `知识点：${contextKp}` : '综合练习'}
</p>
```

### 2.3 低正确率时显示两个操作按钮

**触发条件：** `accuracy < 60 && resultData`（与现有横幅条件相同）

**替换现有 Modal Footer 的低正确率横幅**（现在是一个横幅+一个按钮），改为在 Footer 内独立展示两个按钮：

```jsx
{accuracy < 60 && resultData && (
  <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
    <div className="flex items-start gap-3 mb-3">
      <span className="material-symbols-outlined text-amber-500 flex-shrink-0 mt-0.5">warning</span>
      <div>
        <p className="text-body-md font-medium text-amber-800">
          本次正确率较低（{accuracy}%）{contextKp ? `·「${contextKp}」` : ''}
        </p>
        <p className="text-label-sm text-amber-600 mt-0.5">选择下一步：</p>
      </div>
    </div>
    <div className="flex gap-2">
      {/* 再练一遍：直接跳回 quiz，用同一知识点的个性化题 */}
      {(contextKp || contextNodeId) && (
        <button
          onClick={() => {
            const params = new URLSearchParams({ course_id: activeCourseId });
            if (contextSource === 'personalized' && contextKp) {
              params.set('source', 'personalized');
              params.set('knowledge_point', contextKp);
            } else if (contextNodeId) {
              params.set('node_id', contextNodeId);
            }
            navigate(`/quiz?${params.toString()}`);
          }}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border-2 border-amber-400 text-amber-700 rounded-xl text-label-sm font-bold hover:bg-amber-100 active:scale-95 transition-all"
        >
          <span className="material-symbols-outlined text-[16px]">replay</span>
          再练一遍
        </button>
      )}
      {/* 生成新一批：调 generate API，后台异步，跳个性化资源页 */}
      <button
        onClick={handleGenerateWrongAnswerQuiz}
        disabled={generating}
        className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-amber-500 text-white rounded-xl text-label-sm font-bold hover:bg-amber-600 active:scale-95 transition-all disabled:opacity-50"
      >
        {generating
          ? <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
          : <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
        }
        {generating ? '生成中...' : '生成新一批'}
      </button>
    </div>
    {generateError && <p className="text-error text-label-sm mt-2">{generateError}</p>}
  </div>
)}
```

### 2.4 generate 调用带 knowledge_point

修改 `handleGenerateWrongAnswerQuiz`，在 payload 里加入 `knowledge_point`：

```js
const payload = {
  course_id: activeCourseId,
  generate_type: 'quiz',
  source_type: 'quiz_wrong_answer',
  count: 5,
};
if (wrongQuestionIds.length > 0) payload.wrong_question_ids = wrongQuestionIds;
if (contextKp) payload.knowledge_point = contextKp;  // 新增
```

---

## 3. 完整用户流程

```
学习路径 → 点节点练题（?node_id=xxx）
  └─ Quiz 加载公共题 → 答完提交
       └─ state: { result, quizContext: { node_id, knowledge_point, source:null } }
            └─ PracticeResult
                 ├─ 正确率 >= 60% → 正常返回主页/再练
                 └─ 正确率 < 60%
                      ├─ [再练一遍] → /quiz?node_id=xxx → 同节点再来
                      └─ [生成新一批] → generate({kp=xxx, wrong_ids=[...]}) → 个性化资源页

个性化资源页 → 点"开始练习"（?source=personalized&knowledge_point=xxx）
  └─ Quiz 加载个性化题 → 答完提交
       └─ state: { result, quizContext: { node_id:null, knowledge_point:xxx, source:'personalized' } }
            └─ PracticeResult
                 ├─ 正确率 >= 60% → 掌握了，返回主页
                 └─ 正确率 < 60%
                      ├─ [再练一遍] → /quiz?source=personalized&knowledge_point=xxx → 同批再来
                      └─ [生成新一批] → generate({kp=xxx}) → 新批次个性化题
```

---

## 4. 不改动的部分

- 后端所有接口不变
- PersonalizedResources.jsx 不变（已有正确的跳转逻辑）
- GenerateModal.jsx 不变
- 数据库不变

---

## 5. 验证

```bash
npm run lint && npm run build
```

手动验证路径：
1. 学习路径节点 → 答题全错 → PracticeResult 显示知识点 + 两个按钮
2. "再练一遍" → 跳回同节点 quiz，题目正常加载
3. "生成新一批" → 跳到个性化资源页，出现 processing 卡片
4. 个性化资源页 → 开始练习 → 答题全错 → PracticeResult 显示知识点 + 两个按钮
5. "再练一遍" → 跳回 personalized quiz，题目正常加载
