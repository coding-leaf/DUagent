# LearningPath 节点资源接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 LearningPath 页面点击节点后底部展示真实资源入口，打通"学习路径 → 资源"链路。

**Architecture:** 7 个 task 依序执行：OpenAPI → Backend → Backend 测试 → Frontend service → Frontend 状态与面板 → 占位删除 → 验证收口。每 task 独立提交。Backend 只做字段补全（id + 截断），不新增表或 Agent 调用；Frontend 只消费已有契约。

**Tech Stack:** OpenAPI JSON, FastAPI (Python), React (JavaScript), Vite

**依据 Spec：** `docs/superpowers/specs/2026-06-06-learning-path-node-resources-design.md`

---

### Task 1: OpenAPI — 更新 NodeResources schema

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json:1617-1652`

**目标：** `weak_point_tutorials[].items.properties` 增加 `id`，`chapter_materials[].items.properties` 增加 `id`，`weak_point_tutorials[].items.properties.content` 标注为摘要。

- [ ] **Step 1: 验证 JSON 当前有效**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
jq empty docs/10-client-api/Client-API.openapi.json
```
Expected: no output (valid JSON).

- [ ] **Step 2: 更新 NodeResources schema**

当前 `weak_point_tutorials` items properties（约第 1626-1629 行）：
```json
"properties": {
  "title": { "type": "string" },
  "content": { "type": "string" }
}
```
替换为：
```json
"properties": {
  "id": { "type": "string", "description": "资源 ID，可跳转到 /resource/:id" },
  "title": { "type": "string" },
  "content": { "type": "string", "description": "正文摘要/预览，非完整正文（Backend 截断为前约 160 字符）" }
}
```

当前 `chapter_materials` items properties（约第 1639-1644 行）：
```json
"properties": {
  "title": { "type": "string" },
  "type": { "type": "string", "description": "document / mindmap / reading / code" },
  "url": { "type": "string" }
}
```
替换为：
```json
"properties": {
  "id": { "type": "string", "description": "资源 ID，可跳转到 /resource/:id" },
  "title": { "type": "string" },
  "type": { "type": "string", "description": "document / mindmap / reading / code" },
  "url": { "type": "string" }
}
```

- [ ] **Step 3: 验证 JSON 仍然有效**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
jq empty docs/10-client-api/Client-API.openapi.json
```
Expected: no output.

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add docs/10-client-api/Client-API.openapi.json
git commit -m "OpenAPI NodeResources 补充 weak_point_tutorials 和 chapter_materials 的 id 字段"
```

---

### Task 2: Backend — get_node_resources 加 id + content 截断

**Files:**
- Modify: `../backend/app/api/v1/learning_path.py:370-383`（weak_point_tutorials 构建）
- Modify: `../backend/app/api/v1/learning_path.py:403-418`（chapter_materials 构建）

**注意：** `weak_point_tutorials[].content` 从完整正文改为前 160 字符摘要。

- [ ] **Step 1: 修改 weak_point_tutorials 构建（约第 370-383 行）**

当前代码：
```python
    for r in res_result.scalars().all():
        weak_point_tutorials.append({
            "title": r.title,
            "content": r.content or "",
        })
```
替换为：
```python
    for r in res_result.scalars().all():
        weak_point_tutorials.append({
            "id": r.id,
            "title": r.title,
            "content": (r.content or "")[:160],
        })
```

- [ ] **Step 2: 修改 chapter_materials 构建（约第 403-418 行）**

当前代码：
```python
        for r in ch_result.scalars().all():
            chapter_materials.append({
                "title": r.title,
                "type": r.type,
                "url": r.url or "",
            })
```
替换为：
```python
        for r in ch_result.scalars().all():
            chapter_materials.append({
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "url": r.url or "",
            })
```

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/app/api/v1/learning_path.py
git commit -m "Backend 节点资源接口补充 id 字段并截断 content 为 160 字符摘要"
```

---

### Task 3: Backend 测试 — 覆盖 id 字段和 content 截断

**Files:**
- Create: `../backend/tests/test_node_resources.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Integration tests for GET /api/v1/learning-path/nodes/{node_id}/resources.

Covers: 403 unauthorized course access, 200 with id fields present,
weak_point_tutorials[].content truncated to 160 chars, chapter_materials[].id present.

Requires MySQL or SQLite.

Run: python -m pytest tests/test_node_resources.py -v
"""
import asyncio
import os
import pytest
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_node_resources.db",
)

from app.db.session import async_session_factory, init_db
from httpx import AsyncClient, ASGITransport

asyncio.run(init_db())

from app.main import app
from app.models.user import RegistrationCode
from app.models.course import Course, CourseEnrollment
from app.models.others import LearningPath, Resource, CourseKnowledgeGraph
from app.models.quiz import QuizQuestion


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))
    return d["captcha_token"], ans


async def _register_and_login(client, code, email, username):
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post("/api/v1/auth/register", json={
        "registration_code": code, "email": email, "password": "Abc12345",
        "username": username, "captcha_token": ct_token, "captcha_code": ct_ans,
    })
    assert r.status_code == 201, f"Register failed: {r.status_code} {r.json()}"
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Abc12345",
        "captcha_token": ct_token, "captcha_code": ct_ans,
    })
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}, r.json()["data"]["user_id"]


@pytest.mark.asyncio
async def test():
    transport = ASGITransport(app=app)
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        tag = "OK" if cond else "FAIL"
        print(f"  {tag}  {name}")
        if cond:
            ok += 1
        else:
            fail += 1
        return cond

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ===== Seed users =====
        codes = [
            RegistrationCode(code=f"stu_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"stu2_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"tea_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            student_code = codes[0].code
            student2_code = codes[1].code
            teacher_code = codes[2].code

        stu_headers, stu_id = await _register_and_login(
            client, student_code, f"stu_{uuid.uuid4().hex[:8]}@test.com", f"stu_{uuid.uuid4().hex[:8]}")
        stu2_headers, stu2_id = await _register_and_login(
            client, student2_code, f"stu2_{uuid.uuid4().hex[:8]}@test.com", f"stu2_{uuid.uuid4().hex[:8]}")
        tea_headers, tea_id = await _register_and_login(
            client, teacher_code, f"tea_{uuid.uuid4().hex[:8]}@test.com", f"tea_{uuid.uuid4().hex[:8]}")

        # ===== Create course =====
        r = await client.post("/api/v1/courses", json={"name": "NodeRes Test"}, headers=tea_headers)
        assert r.status_code == 201, f"Create course failed: {r.status_code} {r.json()}"
        course_data = r.json()["data"]
        course_id = course_data["id"]
        course_code = course_data.get("course_code", course_data.get("code", ""))

        join_r = await client.post("/api/v1/courses/join", json={"course_code": course_code}, headers=stu_headers)
        assert join_r.status_code == 200, f"Join failed: {join_r.status_code} {join_r.json()}"

        # ===== Seed LearningPath =====
        node_id = "node_001"
        node_name = "AVL树旋转"
        long_content = "X" * 300  # 300 chars, >160

        async with async_session_factory() as db:
            lp = LearningPath(
                user_id=stu_id,
                course_id=course_id,
                nodes=[{"id": node_id, "name": node_name, "status": "in_progress", "mastery": 50, "order": 1}],
                edges=[],
                current_node_id=node_id,
                current_node_name=node_name,
            )
            db.add(lp)
            # Resource for weak_point_tutorials (matched by knowledge_point == node_name)
            db.add(Resource(id="res_wp", course_id=course_id, title="弱项讲解", type="document",
                            knowledge_point=node_name, chapter="ch1", content=long_content))
            # Resource for chapter_materials (matched by chapter from KG)
            db.add(Resource(id="res_cm", course_id=course_id, title="章节资料", type="reading",
                            knowledge_point="other", chapter="ch1", content="章节内容"))
            # Knowledge graph for chapter lookup
            db.add(CourseKnowledgeGraph(
                course_id=course_id,
                nodes=[{"id": node_id, "name": node_name, "chapter": "ch1"}],
                edges=[],
            ))
            # QuizQuestion for exercises
            db.add(QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point=node_name,
                                type="single_choice", content="What is AVL?",
                                options=["A","B","C","D"], correct_answer="A"))
            await db.commit()

        # ===== 1. 403 — student not enrolled =====
        print("\n-- 1. 403 no course access --")
        r = await client.get(
            f"/api/v1/learning-path/nodes/{node_id}/resources?course_id={course_id}",
            headers=stu2_headers)
        chk("403 student not enrolled", r.status_code == 403)

        # ===== 2. 200 — id fields present =====
        print("\n-- 2. id fields present --")
        r = await client.get(
            f"/api/v1/learning-path/nodes/{node_id}/resources?course_id={course_id}",
            headers=stu_headers)
        chk("200 success", r.status_code == 200)
        data = r.json()["data"]
        chk("node_id present", data.get("node_id") == node_id)
        chk("node_name present", data.get("node_name") == node_name)

        # weak_point_tutorials
        wp = data.get("weak_point_tutorials", [])
        chk("weak_point_tutorials non-empty", len(wp) > 0)
        if len(wp) > 0:
            chk("weak_point_tutorials[0].id present", wp[0].get("id") == "res_wp")
            chk("weak_point_tutorials[0].title present", wp[0].get("title") == "弱项讲解")
            chk("weak_point_tutorials[0].content is str", isinstance(wp[0].get("content"), str))
            chk("weak_point_tutorials[0].content truncated to 160",
                len(wp[0]["content"]) == 160)
            chk("weak_point_tutorials[0].content is prefix",
                long_content.startswith(wp[0]["content"]))

        # chapter_materials
        cm = data.get("chapter_materials", [])
        chk("chapter_materials non-empty", len(cm) > 0)
        if len(cm) > 0:
            chk("chapter_materials[0].id present", cm[0].get("id") == "res_cm")
            chk("chapter_materials[0].title present", cm[0].get("title") == "章节资料")
            chk("chapter_materials[0].type present", cm[0].get("type") == "reading")

        # exercises
        ex = data.get("exercises", [])
        chk("exercises non-empty", len(ex) > 0)
        if len(ex) > 0:
            chk("exercises[0].id present", "id" in ex[0])
            chk("exercises[0].type present", ex[0].get("type") == "single_choice")

        # full_exercise_set
        fe = data.get("full_exercise_set", [])
        chk("full_exercise_set non-empty", len(fe) > 0)

        # ===== 3. empty node (no matching resources) =====
        print("\n-- 3. empty resources --")
        r = await client.get(
            f"/api/v1/learning-path/nodes/nonexistent_node/resources?course_id={course_id}",
            headers=stu_headers)
        chk("empty node -> 200", r.status_code == 200)
        edata = r.json()["data"]
        chk("empty weak_point_tutorials", edata.get("weak_point_tutorials") == [])
        chk("empty exercises", edata.get("exercises") == [])
        chk("empty chapter_materials", edata.get("chapter_materials") == [])

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0, f"{fail} check(s) FAIL"
    return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
```

- [ ] **Step 2: 运行测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
rm -f test_node_resources.db
python -m pytest tests/test_node_resources.py -v --no-header -p no:logging -s 2>&1 | grep -E "^\s*(--|[0-9]+\.|OK|FAIL|Total|PASSED)"
```
Expected: all OK, 0 FAIL, PASSED.

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/tests/test_node_resources.py
git commit -m "测试: 节点资源接口 id 字段和 content 截断验证"
```

---

### Task 4: Frontend service — learning.js 新增 getNodeResources

**Files:**
- Modify: `src/api/services/learning.js`

- [ ] **Step 1: 追加方法**

在 `getResourceDetail` 之后追加：

```javascript
  getNodeResources(nodeId, courseId) {
    return apiClient.get(`/learning-path/nodes/${nodeId}/resources`, {
      params: { course_id: courseId }
    });
  }
```

完整文件变为：
```javascript
import apiClient from '../client';

export const learningService = {
  getLearningPath(courseId) {
    return apiClient.get('/learning-path', { params: { course_id: courseId } });
  },
  refreshLearningPath(courseId) {
    return apiClient.post('/learning-path/refresh', { course_id: courseId });
  },
  getResources(params) {
    return apiClient.get('/resources', { params });
  },
  refreshEvaluation() {
    return apiClient.post('/evaluation/refresh');
  },
  triggerResourceGeneration(params) {
    return apiClient.post('/resources/generate', params);
  },
  getTaskStatus(taskId) {
    return apiClient.get(`/tasks/${taskId}`);
  },
  getResourceDetail(id) {
    return apiClient.get(`/resources/${id}`);
  },
  getNodeResources(nodeId, courseId) {
    return apiClient.get(`/learning-path/nodes/${nodeId}/resources`, {
      params: { course_id: courseId }
    });
  }
};
```

- [ ] **Step 2: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS (no errors).

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/learning.js
git commit -m "learningService 新增 getNodeResources"
```

---

### Task 5: Frontend page — LearningPath.jsx 状态管理 + 点击 + 资源面板

**Files:**
- Modify: `src/pages/LearningPath.jsx`

**注意：** Task 5 和 Task 6 操作同一文件。Task 5 专注于新增功能（状态、点击、面板），Task 6 专注于清理旧内容（节点卡片内占位文案 + 未使用函数）。Task 5 的底部面板替换已覆盖了 3 张静态占位卡的删除；Task 6 不需再确认静态卡，直接处理节点卡片内占位即可。

- [ ] **Step 1: 新增 state**

在 `const [loading, setLoading] = useState(true);` 之后追加：
```javascript
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [nodeResources, setNodeResources] = useState(null);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [showFullExercises, setShowFullExercises] = useState(false);
```

- [ ] **Step 2: 更新 import，新增 fetchNodeResources 函数 + 默认选中 effect**

先将文件顶部 React import 从：
```javascript
import { useState, useEffect } from 'react';
```
改为：
```javascript
import { useState, useEffect, useCallback } from 'react';
```

然后在 `useEffect` 获取 learningPath 之后，新增：

```javascript
  // 获取节点资源
  const fetchNodeResources = useCallback(async (nodeId) => {
    if (!nodeId || !activeCourseId) return;
    try {
      setResourcesLoading(true);
      const res = await learningService.getNodeResources(nodeId, activeCourseId);
      if (res.code === 200) {
        setNodeResources(res.data);
      }
    } catch (error) {
      console.error("Failed to fetch node resources:", error);
      setNodeResources(null);
    } finally {
      setResourcesLoading(false);
    }
  }, [activeCourseId]);

  // 默认选中节点（learningPath 加载完成后）
  useEffect(() => {
    if (!learningPath?.nodes?.length) return;
    // 优先 current_position.node_id
    const cpId = learningPath.current_position?.node_id;
    if (cpId) {
      setSelectedNodeId(cpId);
      return;
    }
    // 然后第一个 in_progress
    const ip = learningPath.nodes.find(n => n.status === 'in_progress');
    if (ip) { setSelectedNodeId(ip.id); return; }
    // 然后第一个 recommended
    const rec = learningPath.nodes.find(n => n.status === 'recommended');
    if (rec) { setSelectedNodeId(rec.id); return; }
    // 最后第一个非 pending 节点
    const first = learningPath.nodes.find(n => n.status !== 'pending');
    if (first) { setSelectedNodeId(first.id); return; }
  }, [learningPath]);

  // selectedNodeId 变化时获取资源
  useEffect(() => {
    if (selectedNodeId) {
      fetchNodeResources(selectedNodeId);
      setShowFullExercises(false);
    }
  }, [selectedNodeId, fetchNodeResources]);
```

- [ ] **Step 3: 节点卡片加 onClick 和高亮**

**completed 节点**（约第 93 行的外层 div）改为：
```javascript
<div key={node.id}
  onClick={() => setSelectedNodeId(node.id)}
  className={`relative z-10 flex-shrink-0 px-sm flex flex-col items-center group w-80 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-cyan-400 rounded-xl' : ''}`}>
```

**in_progress 节点**（约第 116 行的外层 div）改为：
```javascript
<div key={node.id}
  onClick={() => setSelectedNodeId(node.id)}
  className={`relative z-10 flex-shrink-0 w-80 px-sm flex flex-col items-center group cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-cyan-400 rounded-xl' : ''}`}>
```

**pending 节点**（现有 else 分支，约第 145 行）不加 onClick，保持现有样式（锁图标 + 灰显）。

**recommended 节点**：当前代码没有 recommended 独立分支——它落在 `else`（pending/locked 样式）分支。需要为 recommended 新增独立分支，放在 `in_progress` 分支之后、`else` 之前：

```javascript
                    } else if (node.status === 'recommended') {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 w-72 px-sm flex flex-col items-center group cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-cyan-400 rounded-xl' : ''}`}>
                          <div className="w-12 h-12 rounded-full bg-cyan-100 flex items-center justify-center text-cyan-600 mb-sm border-2 border-cyan-200">
                            <span className="material-symbols-outlined">auto_awesome</span>
                          </div>
                          <div className="bg-white p-sm rounded-xl border border-cyan-200 shadow-sm w-full">
                            <span className="text-label-sm text-cyan-600 font-bold mb-xs block">阶段 {node.order}</span>
                            <p className="text-body-md font-bold mb-xs">{node.name}</p>
                            <div className="h-1 w-full bg-gray-100 rounded-full overflow-hidden mb-sm">
                              <div className="h-full bg-cyan-300 w-0"></div>
                            </div>
                            <p className="text-[11px] text-cyan-500">推荐预习节点</p>
                          </div>
                        </div>
                      );
                    }
```

- [ ] **Step 4: 底部面板 — 替换 3 张静态占位卡**

将 `{/* Bottom Modules: Recommendations */}` 整块（约第 170-210 行，含知识导图推荐、课件讲义推荐、混合练习集推荐三张卡）替换为：

```javascript
          {/* Node Resources Panel */}
          {selectedNodeId && (
            <section className="mt-8 space-y-6">
              <h3 className="font-h3 text-h3 flex items-center gap-2">
                <span className="material-symbols-outlined text-cyan-600">library_books</span>
                当前节点资源
                {nodeResources?.node_name && (
                  <span className="text-body-md text-secondary font-normal">— {nodeResources.node_name}</span>
                )}
              </h3>

              {resourcesLoading ? (
                <div className="flex justify-center py-12">
                  <span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span>
                </div>
              ) : nodeResources ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* 1. 薄弱点讲解 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-orange-50 rounded-lg text-orange-600">
                        <span className="material-symbols-outlined">lightbulb</span>
                      </div>
                      <h4 className="font-bold text-on-surface">薄弱点讲解</h4>
                    </div>
                    {nodeResources.weak_point_tutorials?.length > 0 ? (
                      <div className="space-y-3">
                        {nodeResources.weak_point_tutorials.map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <p className="text-sm font-bold text-on-surface mb-1">{item.title}</p>
                            <p className="text-xs text-secondary line-clamp-2 mb-2">{item.content || ''}</p>
                            {item.id ? (
                              <Link to={`/resource/${item.id}`} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1">
                                查看资源 <span className="material-symbols-outlined text-xs">arrow_forward</span>
                              </Link>
                            ) : (
                              <span className="text-xs text-gray-400">暂无详情</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 py-4 text-center">该节点暂无薄弱点讲解</p>
                    )}
                  </div>

                  {/* 2. 节点练习 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                        <span className="material-symbols-outlined">quiz</span>
                      </div>
                      <h4 className="font-bold text-on-surface">节点练习</h4>
                    </div>
                    {nodeResources.exercises?.length > 0 ? (
                      <div className="space-y-3">
                        {nodeResources.exercises.map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[10px] rounded font-bold">
                                {item.type === 'single_choice' ? '单选' : item.type === 'multi_choice' ? '多选' : item.type}
                              </span>
                            </div>
                            <p className="text-xs text-secondary line-clamp-2">{item.content || ''}</p>
                          </div>
                        ))}
                        <Link to="/quiz" className="w-full block text-center py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors">
                          进入练习
                        </Link>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 py-4 text-center">该节点暂无练习</p>
                    )}
                  </div>

                  {/* 3. 章节资料 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
                        <span className="material-symbols-outlined">menu_book</span>
                      </div>
                      <h4 className="font-bold text-on-surface">章节资料</h4>
                    </div>
                    {nodeResources.chapter_materials?.length > 0 ? (
                      <div className="space-y-3">
                        {nodeResources.chapter_materials.map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] rounded font-bold">
                                {item.type || '资料'}
                              </span>
                              <p className="text-sm font-bold text-on-surface">{item.title}</p>
                            </div>
                            {item.id ? (
                              <Link to={`/resource/${item.id}`} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1 mt-1">
                                查看资源 <span className="material-symbols-outlined text-xs">arrow_forward</span>
                              </Link>
                            ) : (
                              <span className="text-xs text-gray-400">暂无详情</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 py-4 text-center">该节点暂无章节资料</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-gray-100 p-8 text-center">
                  <p className="text-sm text-gray-400">无法加载节点资源</p>
                </div>
              )}

              {/* 4. 全部练习集（折叠） */}
              {nodeResources?.full_exercise_set?.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                  <button
                    onClick={() => setShowFullExercises(!showFullExercises)}
                    className="w-full flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <div className="p-2 bg-purple-50 rounded-lg text-purple-600">
                        <span className="material-symbols-outlined">list_alt</span>
                      </div>
                      <h4 className="font-bold text-on-surface text-left">
                        全部练习集
                        <span className="text-xs text-secondary font-normal ml-2">共 {nodeResources.full_exercise_set.length} 题</span>
                      </h4>
                    </div>
                    <span className={`material-symbols-outlined text-gray-400 transition-transform ${showFullExercises ? 'rotate-180' : ''}`}>
                      expand_more
                    </span>
                  </button>
                  {showFullExercises && (
                    <div className="mt-4 space-y-2 max-h-96 overflow-y-auto">
                      {nodeResources.full_exercise_set.slice(0, 10).map((item, i) => (
                        <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="px-1.5 py-0.5 bg-purple-100 text-purple-700 text-[10px] rounded font-bold">
                              {item.type === 'single_choice' ? '单选' : item.type === 'multi_choice' ? '多选' : item.type}
                            </span>
                          </div>
                          <p className="text-xs text-secondary line-clamp-2">{item.content || ''}</p>
                        </div>
                      ))}
                      {nodeResources.full_exercise_set.length > 10 && (
                        <p className="text-xs text-gray-400 text-center pt-2">查看更多请进入练习</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
```

- [ ] **Step 5: 验证 build**
注意：Task 5 结束后可能有旧占位卡残留导致的未使用变量。此为预期，Task 6 清理。

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build
```
Expected: build 成功。

- [ ] **Step 6: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/LearningPath.jsx
git commit -m "LearningPath 节点点击和底部资源面板接入"
```

---

### Task 6: Frontend page — 删除底部静态占位卡 + 节点占位文案

**Files:**
- Modify: `src/pages/LearningPath.jsx`

- [ ] **Step 1: 删除 completed 节点内的资源/习题占位**

删除约第 103-109 行的整块 div：
```javascript
                            <div className="space-y-sm pt-sm border-t border-gray-50">
                              <div className="space-y-1">
                                <p className="text-[11px] text-error">知识点推荐将在路径节点接入真实数据后展示</p>
                              </div>
                              <div className="space-y-1">
                                <p className="text-[11px] text-on-surface-variant">配套习题将在节点资源接入后展示</p>
                              </div>
                            </div>
```

- [ ] **Step 2: in_progress 节点内删除习题占位（保留 Agent 提示）**

将：
```javascript
                                <span>进度: {node.mastery}%</span>
                                <span>关键知识点诊断待 Backend 数据接入</span>
```
改为：
```javascript
                                <span>进度: {node.mastery}%</span>
```

Agent 提示（`智能体提示将在路径 Agent 输出接入后展示`）保留不动。

- [ ] **Step 3: 清理未使用的 getCategoryForNode**

如果 `getCategoryForNode` 函数（约第 31-37 行）不再被引用，删除它。

- [ ] **Step 4: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: lint PASS, build PASS.

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/LearningPath.jsx
git commit -m "LearningPath 删除节点卡片内资源/习题占位文案"
```

---

### Task 7: 全量验证 + WORKFLOW 收口

**Files:**
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS.

- [ ] **Step 2: Backend 测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
rm -f test_node_resources.db
python -m pytest tests/test_node_resources.py -v --no-header -p no:logging -s 2>&1 | grep -E "^\s*(--|[0-9]+\.|OK|FAIL|Total|PASSED)"
```
Expected: all OK, 0 FAIL, PASSED.

确认已有测试未回归：
```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m pytest tests/test_resource_detail.py -v --no-header -p no:logging 2>&1 | tail -3
```
Expected: PASSED.

- [ ] **Step 3: OpenAPI JSON 验证**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
jq empty docs/10-client-api/Client-API.openapi.json
```
Expected: no output (valid).

- [ ] **Step 4: 更新 WORKFLOW.md**

在 `## 最近验证` 末尾追加：
```markdown
- 2026-06-06：LearningPath 节点资源接入完成：
  - OpenAPI：NodeResources schema 补充 `weak_point_tutorials[].id`、`chapter_materials[].id`，`content` 标注为摘要
  - Backend：`get_node_resources` 补充 `id` 字段，`weak_point_tutorials[].content` 截断为 160 字符
  - Backend 测试：覆盖 403 / id 字段 / content 160 截断 / 空资源
  - Frontend：`learningService.getNodeResources`；LearningPath.jsx 底部动态资源面板替换 3 张静态占位卡
  - 节点点击：completed/in_progress/recommended 可点，pending 不可点；默认选中 current_node
  - 删除 completed/in_progress 节点内资源/习题占位文案，保留 Agent 提示占位
  - `npm run lint` / `npm run build` / Backend pytest 通过。
```

并将 `## 当前判断` 中的阶段二状态更新为包含本次进展。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "docs: 记录 LearningPath 节点资源接入完成"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ Task 1-7 覆盖 OpenAPI/Backend/Backend 测试/Frontend service/Frontend page/占位删除/收口。

**2. 无占位符：** ✅ 所有步骤含完整代码，无 TBD/TODO。

**3. 类型一致性：** ✅ `id` 字段在 OpenAPI (string) → Backend (`r.id`) → Frontend (`/resource/${item.id}`) 保持一致。`content` 截断在 Backend 侧完成（`:160`），前端不额外处理。

**4. 边界注意：**
- `recommended` 状态在前端当前代码中没有独立渲染分支，Task 5 Step 3 给出了处理指引
- Task 5 和 Task 6 操作同一文件，已拆分功能新增/删除为独立 task
- `full_exercise_set` 展开后 `slice(0, 10)` + "查看更多请进入练习"，与 spec 一致
