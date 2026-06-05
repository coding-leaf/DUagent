# 阶段二第一轮 — 联调断层收敛 / Mock 分支清理 + Admin 契约修正 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清除前端 service 中 5 个 mock 分支路径，保留并标记 1 个阶段二 P0 阻塞 mock 分支（getConsoleInsights），修正 AdminConsole 与 OpenAPI/Backend 之间的契约不对齐，为阶段二联调建立干净的接口边界。

**Architecture:** 仅做前端删除与参数/字段适配，不涉及 Backend、Agent 或新增 API 端点。每个 task 改变一个独立关注点，可单独 lint/build 验证、单独提交。`chat.js` mock 分支保留（`VITE_USE_MOCK` 开发辅助）。

**Tech Stack:** JavaScript, Vite, Playwright (E2E), ESLint

**依据 Spec：** `docs/superpowers/specs/2026-06-05-phase2-gap-analysis.md` 组 2（#9-#14）和 #18

---

## 前置：审批门

- [ ] **Step 0: 输出分析摘要并等待用户批准**

向用户输出：

```markdown
## 第一轮清理范围

### 删除 5 个 mock 分支（仅前端，不碰 Backend/Agent）

| 文件 | mock 路径 | 真实端点 | Spec # |
|------|----------|---------|--------|
| teaching.js:8-10 | /api/v1/teacher/classes | GET /courses | #9 |
| teaching.js:29-31 | /api/v1/course/{id}/students | GET /teaching/classes/{id}/students | #10 |
| teaching.js:80-82 | /api/v1/teacher/students/{id}/report | GET /teaching/classes/{id}/students/{id}/learning | #12 |
| admin.js:23-25 | /admin/logs/agents | GET /admin/logs/agent | #13 |
| admin.js:31-33 | /admin/logs/system | GET /admin/logs/operations | #14 |

### 保留并标记（本轮不改代码，仅记录到 WORKFLOW.md）

| 位置 | 问题 | 处理 |
|------|------|------|
| teaching.js:61-68 getConsoleInsights | mock + 真实 data:null | 本轮不改代码，仅记录到 WORKFLOW.md |
| TeacherConsole.jsx:214 useMock && | 守卫 Insights 区块 | 本轮不改代码，仅记录到 WORKFLOW.md |

### AdminConsole 契约修正（3 处前端适配）

| 位置 | 问题 | 处理 |
|------|------|------|
| AdminConsole.jsx:21 | { search } → OpenAPI 参数是 keyword | 改参数名 |
| AdminConsole.jsx:188-198 | u.status / u.last_login → Backend 不返回 | 删 status 列 + 封禁按钮；last_login 改 N/A |
| AdminConsole.jsx:66-74,199-218 | 封禁（PUT { status }）+ 删除（DELETE）→ 后端 DELETE 是软删除（is_active=False），列表查询按 is_deleted 过滤，不返回 status/is_active。语义未对齐 | 删封禁按钮（Backend 不支持 status 字段）；暂停/移除删除按钮（DELETE 语义待契约确认：软删除/停用/封禁） |

### 不在此轮处理

- chat.js mock 分支（保留为 VITE_USE_MOCK 开发辅助）
- 新增班级洞察端点（下一轮）
- 新增 Backend/Agent 字段（下一轮）

### 验证命令

- npm run lint
- npm run build
- npm run test:e2e（需 Backend + Agent + MySQL duagent_test 在线）
```

等待用户回复 "批准" 后进入 Task 1。

---

### Task 1: 清理 teaching.js getClasses mock 分支

**Files:**
- Modify: `src/api/services/teaching.js`

**背景：** `getClasses` 的 mock 分支调用不在 OpenAPI 中的 `/api/v1/teacher/classes`。真实分支已对接 `GET /courses` 并有字段适配层。

- [ ] **Step 1: 重新读取文件后删除 mock 路径**

Run:
```bash
cat /home/yezisama/workspace/workflow/EDUagent/frontend/src/api/services/teaching.js
```

删除第 8-10 行的 mock 路径条件分支（`if (useMock) { return client.get('/api/v1/teacher/classes'); }`），仅保留真实端点逻辑。

修改后的 `getClasses` 方法应为：

```javascript
  // 获取教师名下的班级/课程列表
  getClasses: async () => {
    const res = await client.get('/courses');
    if (res.code === 200 && res.data && res.data.courses) {
      return {
        code: 200,
        message: 'success',
        data: res.data.courses.map(c => ({
          id: c.id,
          name: c.name,
          topic: c.description || c.name,
          students: c.student_count || 0
        }))
      };
    }
    return res;
  },
```

- [ ] **Step 2: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/teaching.js
git commit -m "清理 teaching getClasses mock 分支"
```

---

### Task 2: 清理 teaching.js getClassStudents mock 分支

**Files:**
- Modify: `src/api/services/teaching.js`

**背景：** mock 路径 `/api/v1/course/{id}/students` 不在 OpenAPI。真实端点 `GET /teaching/classes/{courseId}/students` 已对接。

- [ ] **Step 1: 删除 mock 路径**

删除 `getClassStudents` 方法中的 mock 条件分支（第 29-31 行：`if (useMock) { return client.get(...); }`），仅保留真实端点逻辑。

修改后的 `getClassStudents` 方法应为：

```javascript
  // 获取某个课程的学生列表
  getClassStudents: async (courseId) => {
    const res = await client.get(`/teaching/classes/${courseId}/students`);
    if (res.code === 200 && res.data && res.data.students) {
      const adapted = res.data.students.map((s, i) => {
        const colors = ['primary', 'secondary', 'tertiary', 'error'];
        const colorType = colors[i % colors.length];
        const lastName = s.real_name ? s.real_name.charAt(0) : (s.username ? s.username.charAt(0) : '学');
        return {
          user_id: s.id,
          username: s.real_name || s.username || '学生',
          english_name: s.username || 'Student',
          student_id: s.student_id || '20260000',
          avatar_text: lastName,
          avatar_color: `bg-${colorType}-container/20 text-${colorType}`,
          major: s.major,
          grade: s.grade,
          joined_at: s.joined_at
        };
      });
      return {
        code: 200,
        message: 'success',
        data: adapted
      };
    }
    return res;
  },
```

- [ ] **Step 2: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/teaching.js
git commit -m "清理 teaching getClassStudents mock 分支"
```

---

### Task 3: 清理 teaching.js getStudentReport mock 分支

**Files:**
- Modify: `src/api/services/teaching.js`

**背景：** mock 路径 `/api/v1/teacher/students/{id}/report` 不在 OpenAPI。真实端点 `GET /teaching/classes/{class_id}/students/{student_id}/learning` 已对接。

- [ ] **Step 1: 删除 mock 路径**

删除 `getStudentReport` 方法中的 mock 条件分支（第 80-82 行），仅保留真实端点逻辑：

```javascript
  // 获取特定学生的详细学情报告
  getStudentReport: async (classId, studentId) => {
    let actualClassId = classId;
    let actualStudentId = studentId;
    if (studentId === undefined) {
      actualStudentId = classId;
      actualClassId = localStorage.getItem('course_id') || 'default_course';
    }

    return client.get(`/teaching/classes/${actualClassId}/students/${actualStudentId}/learning`);
  }
```

**注意：** 完成此 Task 后检查 teaching.js 顶部 `const useMock = ...` 是否被 `getConsoleInsights` 引用。`getConsoleInsights` 内部使用 `useMock`（第 61 行的 if 条件），因此 `useMock` 声明仍需保留。不要删除 `useMock`。

- [ ] **Step 2: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/teaching.js
git commit -m "清理 teaching getStudentReport mock 分支"
```

---

### Task 4: 清理 admin.js getAgentLogs mock 分支

**Files:**
- Modify: `src/api/services/admin.js`

**背景：** mock 路径 `/admin/logs/agents`（复数）与真实端点 `/admin/logs/agent`（单数）路径不同。

- [ ] **Step 1: 删除 mock 条件分支，仅保留真实端点**

将 `getAgentLogs` 方法简化为：

```javascript
  // 拉取核心调度器与子智能体的运行日志
  getAgentLogs: async (params) => {
    return apiClient.get('/admin/logs/agent', { params });
  },
```

- [ ] **Step 2: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/admin.js
git commit -m "清理 admin getAgentLogs mock 分支"
```

---

### Task 5: 清理 admin.js getSystemLogs mock 分支 + 移除 useMock 声明

**Files:**
- Modify: `src/api/services/admin.js`

**背景：** mock 路径 `/admin/logs/system` 与真实端点 `/admin/logs/operations` 路径不同。注意 `AdminConsole.jsx:37` 调用了 `getSystemLogs` 但未消费返回数据。

- [ ] **Step 1: 删除 mock 条件分支，仅保留真实端点**

将 `getSystemLogs` 方法简化为：

```javascript
  // 拉取系统基础日志
  getSystemLogs: async (params) => {
    return apiClient.get('/admin/logs/operations', { params });
  }
```

- [ ] **Step 2: 删除 useMock 声明**

删除第 3 行：
```javascript
const useMock = import.meta.env.VITE_USE_MOCK === 'true';
```

`useMock` 在 admin.js 中仅被 `getAgentLogs` 和 `getSystemLogs` 引用。两个方法都在本轮清理，该声明已无引用。

- [ ] **Step 3: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/admin.js
git commit -m "清理 admin getSystemLogs mock 分支,移除 useMock 声明"
```

---

### Task 6: 修正 AdminConsole 搜索参数 search → keyword

**Files:**
- Modify: `src/pages/AdminConsole.jsx`

**背景：** Spec #18 第①项：OpenAPI/Backend 参数名为 `keyword`，前端传 `search`。

- [ ] **Step 1: 修改调用方参数名**

修改 `AdminConsole.jsx` 第 21 行：

```javascript
// Before:
const res = await adminService.getUsers({ search: searchQuery });
// After:
const res = await adminService.getUsers({ keyword: searchQuery });
```

`adminService.getUsers` 透传 params 给 `apiClient.get('/admin/users', { params })`，无需修改。

- [ ] **Step 2: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/AdminConsole.jsx
git commit -m "修正 AdminConsole 搜索参数 search 改为 keyword"
```

---

### Task 7: 处理 AdminConsole 用户状态字段/封禁与删除动作契约不对齐

**Files:**
- Modify: `src/pages/AdminConsole.jsx`

**背景：** Spec #18 第②③项 + 契约审查发现：

1. **封禁（toggleUserStatus）**：`PUT /admin/users/{id}` 传 `{ status }`，但 OpenAPI `AdminUpdateUserRequest` 和 Backend 均不支持 `status` 字段。**本轮删除封禁按钮。**

2. **删除（deleteUser）**：`DELETE /admin/users/{id}` 实际执行 `target.is_active = False`（软删除），但用户列表查询按 `is_deleted == False` 过滤，不返回 `is_active`/`status` 字段。这意味着：删除后本地乐观移除，但重新拉列表仍会出现。**DELETE 的语义（软删除/停用/封禁）尚未契约明确，本轮一并移除删除按钮，待契约确认后再恢复。**

3. **status 列 + last_login 列**：Backend 不返回这两个字段。**本轮删除 status 列，last_login 改为 N/A。**

**处理方案：**
- 删除 `u.status` 列（表头 + 渲染）
- 删除 `toggleUserStatus` 函数和封禁/解封按钮
- 删除 `deleteUser` 函数和删除按钮（DELETE 语义待确认）
- `u.last_login` 改为 `N/A`
- 保留 `u.role` — Backend 返回此字段
- 表格 colSpan 从 6 改为 4（删除状态列 + 操作列无按钮时保留操作列头但内容为空，或一并删除操作列）

- [ ] **Step 1: 删除 toggleUserStatus 函数（第 66-74 行）和 deleteUser 函数（第 76-84 行）**

删除两个函数块。

- [ ] **Step 2: 删除表头"状态"列和"操作"列**

删除：
```jsx
<th className="px-6 py-4 font-medium">状态</th>
<th className="px-6 py-4 font-medium text-right">操作</th>
```

- [ ] **Step 3: 删除表格行中"状态"列和"操作"列的渲染**

删除 `<td>` 状态列（第 188-195 行）和 `<td>` 操作列（第 199-218 行）。

- [ ] **Step 4: 修改"最后登录"列为 N/A**

改为：
```jsx
<td className="px-6 py-4 text-slate-500 text-xs">N/A</td>
```

- [ ] **Step 5: 更新 colSpan**

将两处 `colSpan="6"`（第 171、173 行）改为 `colSpan="4"`（删除了状态列和操作列）。

- [ ] **Step 6: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 7: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/AdminConsole.jsx
git commit -m "暂停 AdminConsole 封禁和删除动作,待 Admin 用户状态契约确认"
```

---

### Task 8: 全量验证 — lint / build / E2E

**Files:** 无修改（仅验证，不产生提交）

- [ ] **Step 1: 运行 ESLint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS, 0 errors

- [ ] **Step 2: 运行生产构建**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build
```
Expected: PASS（允许已有的 Vite chunk size warning）

- [ ] **Step 3: 运行 E2E 测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run test:e2e
```
Expected: 3/3 passed（需 Backend + Agent + MySQL duagent_test 在线）

---

### Task 9: 更新 WORKFLOW.md

**Files:**
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: 在 "最近验证" 末尾追加第一轮清理记录**

在最后一条验证记录之后追加：

```markdown
- 2026-06-05：阶段二第一轮联调断层收敛 — 清理 5 个 mock 分支 + AdminConsole 契约修正：
  - `teaching.js`：移除 getClasses / getClassStudents / getStudentReport 的 mock 路径
  - `admin.js`：移除 getAgentLogs / getSystemLogs 的 mock 路径，删除 useMock 声明
  - `AdminConsole.jsx`：搜索参数 search → keyword；删除状态列、封禁按钮、删除按钮（DELETE 语义待契约确认）；last_login 改为 N/A
  - 标记为第二轮 P0：`getConsoleInsights` mock + data:null 空实现、`TeacherConsole.jsx` useMock && Insights 守卫
  - 清理后 `npm run lint` / `npm run build` 通过。
```

- [ ] **Step 2: 更新 "下一步建议"**

追加方向建议：

```markdown
- 阶段二第一轮 mock 分支清理已完成。第二轮 P0：新增班级洞察端点（getConsoleInsights 空实现）、移除 TeacherConsole useMock && Insights 守卫。第二轮 P1：教师深度诊断字段扩展、ResourceDetail 页面改造、学习路径节点资源接入、Admin 用户状态/封禁/删除契约确认。
```

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "记录阶段二第一轮 mock 分支清理和契约修正结果"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ 覆盖 spec 组 2 全部 5 条 mock 清理（#9-#10, #12-#14）+ #18 全部 3 处不对齐。未覆盖条目（#1-#8, #11, #15-#17, #19）属于后续轮次。#11（getConsoleInsights mock）本轮保留并记录到 WORKFLOW.md。

**2. 无占位符：** ✅ 所有步骤有完整代码、确切命令与预期输出。

**3. 类型一致性：** ✅ 不涉及新类型/接口定义，均为删除 mock 分支、改参数名、删除 UI 元素。

## 风险评估

| 风险 | 概率 | 缓解 |
|------|------|------|
| 删除 mock 分支后 E2E 失败 | 低 | E2E 运行在真实环境（`VITE_USE_MOCK !== 'true'`），不依赖 mock 路径 |
| AdminConsole 删除状态列+操作列后 colSpan 未同步 | 低 | Task 7 Step 5 明确要求将 colSpan 从 6 改为 4 |
| TeacherConsole 的 useMock 变量在清理后仍被引用 | 已确认 | `useMock` 在 TeacherConsole.jsx 中独立定义，不受 teaching.js 清理影响 |
