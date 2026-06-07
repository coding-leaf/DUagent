# 前端 Service 非契约历史封装清理 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理前端 `src/api/services/` 中未使用且不在 Client API OpenAPI 契约中的历史封装方法，消除阶段一遗留契约疑点。

**Architecture:** 仅做删除操作，不新增任何代码或功能。删除目标：6 个未使用 + 不在 OpenAPI 的 service 方法。保留仍在使用的和在 OpenAPI 中的方法。事后验证 lint/build/e2e 全绿。

**Tech Stack:** JavaScript (no TypeScript), Vite, Playwright (E2E), ESLint

---

## 背景与审查结论

### 当前 OpenAPI 声明的路径（`docs/10-client-api/Client-API.openapi.json`）

```
GET     /auth/captcha
POST    /auth/register
POST    /auth/login
GET     /users/me
PUT     /users/me
GET     /courses
POST    /courses
POST    /courses/join
GET     /teaching/classes/{class_id}/students
GET     /teaching/classes/{class_id}/students/{student_id}
GET     /teaching/classes/{class_id}/students/{student_id}/learning
GET     /admin/users
PUT     /admin/users/{user_id}
DELETE  /admin/users/{user_id}
GET     /admin/logs/agent
GET     /admin/logs/operations
GET     /evaluation
POST    /evaluation/refresh
POST    /profile/initialize
GET     /profile
POST    /profile/refresh
GET     /learning-path
POST    /learning-path/refresh
GET     /learning-path/nodes/{node_id}/resources
GET     /quiz/questions
POST    /quiz/generate
POST    /quiz/submit
GET     /quiz/result
GET     /quiz/history
GET     /resources
POST    /resources/generate
POST    /tutoring/chat
GET     /tutoring/conversations
GET     /tutoring/conversations/{id}
GET     /tasks/{task_id}
POST    /webhooks/agent
```

### 调用关系分析（已通过 grep 全文搜索验证）

**authService** (`src/api/services/auth.js`)：
| 方法 | 调用方 | OpenAPI |
|------|--------|---------|
| `getCurrentUser()` | `AuthContext.jsx:20` | ✅ GET /users/me |
| `getCaptcha()` | `Register.jsx:27`, `Login.jsx:22` | ✅ GET /auth/captcha |
| `login()` | `Login.jsx:45` | ✅ POST /auth/login |
| `register()` | `Register.jsx:60` | ✅ POST /auth/register |
| **`logout()`** | **无调用** | **❌ 未声明** |
| **`refreshToken()`** | **无调用** | **❌ 未声明** |
| **`sendResetPasswordCode()`** | **无调用** | **❌ 未声明** |
| **`resetPassword()`** | **无调用** | **❌ 未声明** |

**profileService** (`src/api/services/profile.js`)：
| 方法 | 调用方 | OpenAPI |
|------|--------|---------|
| `getStudentProfile()` | `StudentProfile.jsx:22` | ✅ GET /profile |
| **`updateProfile()`** | **无调用** | **❌ OpenAPI 无 PUT /profile** |
| `refreshProfile()` | `StudentProfile.jsx:23` | ✅ POST /profile/refresh |
| `getLearningEffects()` | `LearningEffects.jsx:14`, `StudentProfile.jsx:23` | ✅ GET /evaluation |

**courseService** (`src/api/services/course.js`)：
| 方法 | 调用方 | OpenAPI |
|------|--------|---------|
| `getMyCourses()` | `CourseContext.jsx:20` | ✅ GET /courses |
| **`getCourseStudents()`** | **无调用** | **❌ 路径不在 OpenAPI（正确路径：`/teaching/classes/{class_id}/students`）** |
| `createCourse()` | 无调用 | ✅ POST /courses（保留：在 OpenAPI 中） |
| `joinCourse()` | 无调用 | ✅ POST /courses/join（保留：在 OpenAPI 中） |

**注意**：`authService.logout()` 删除不影响现有功能 — `AuthContext.logout()` 仅做客户端 `localStorage.removeItem('access_token')`，不调用后端 API。

---

### Task 0: 执行前审批门（AGENTS.md 要求）

**此步骤必须在任何代码修改之前完成。** 参考 `AGENTS.md:81` 的修改审查要求，在执行计划前向用户输出以下内容并等待批准：

- [ ] **Step 0: 输出分析摘要并等待用户批准**

向用户输出：

```markdown
## 问题分析

阶段一主链路已在真实环境下 E2E 通过，但前端 `src/api/services/` 中存在 6 个历史封装方法：
无调用方 + 不在 `Client-API.openapi.json` 声明中。

## 计划修改文件

| 文件 | 操作 |
|------|------|
| `src/api/services/auth.js` | 删除 logout、refreshToken、sendResetPasswordCode、resetPassword（共 4 个方法） |
| `src/api/services/profile.js` | 删除 updateProfile（1 个方法） |
| `src/api/services/course.js` | 删除 getCourseStudents（1 个方法） |
| `frontend/WORKFLOW.md` | 追加清理记录，更新下一步建议 |

## 修改方案

仅做方法删除，不新增代码。保留仍在使用的所有方法。保留 OpenAPI 中有声明但暂未使用的 `createCourse`、`joinCourse`。

## 影响范围

- 无页面/context 引用这 6 个方法，删除不会产生 import 错误
- 无 API 契约变更，无后端变更
- 不涉及 CSS、路由、状态管理

## 验证命令

npm run lint
npm run build
npm run test:e2e（需 Backend + Agent + MySQL duagent_test 在线）
```

等待用户回复"批准"/"允许"/"开始"后，进入 Task 1。

---

### Task 1: 清理 authService 的 4 个非契约方法

**Files:**
- Modify: `src/api/services/auth.js`

- [ ] **Step 1: 重新读取文件后，用最小 diff 仅删除目标方法**

先 Run：
```bash
cat /home/yezisama/workspace/workflow/EDUagent/frontend/src/api/services/auth.js
```

然后仅删除以下 4 个方法块，保留其余所有代码不变：

删除第 16-18 行：
```javascript
  logout: async () => {
    return apiClient.post('/auth/logout');
  },
```

删除第 20-23 行：
```javascript
  // 刷新 Token
  refreshToken: async (refreshToken) => {
    return apiClient.post('/auth/refresh', { refresh_token: refreshToken });
  },
```

删除第 25-28 行（含上方空行）：
```javascript
  // 发送重置密码验证码
  sendResetPasswordCode: async (email) => {
    return apiClient.post('/auth/reset-password/code', { email });
  },
```

删除第 30-33 行（含上方空行）：
```javascript
  // 重置密码
  resetPassword: async (email, code, newPassword) => {
    return apiClient.post('/auth/reset-password', { email, code, new_password: newPassword });
  }
```

删除后文件末尾的 `};` 前不应有多余空行。

- [ ] **Step 2: 验证 lint 通过**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS, 0 errors / 0 warnings

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/auth.js
git commit -m "清理 authService 非契约历史方法"
```

---

### Task 2: 清理 profileService 的 updateProfile 方法

**Files:**
- Modify: `src/api/services/profile.js`

- [ ] **Step 1: 重新读取文件后，用最小 diff 仅删除 updateProfile**

先 Run：
```bash
cat /home/yezisama/workspace/workflow/EDUagent/frontend/src/api/services/profile.js
```

然后仅删除以下方法块，保留其余所有代码不变：

删除第 8-11 行（含上方空行）：
```javascript
  // 修改个人信息
  updateProfile: async (courseId, data) => {
    return apiClient.put('/profile', data, { params: { course_id: courseId } });
  },
```

- [ ] **Step 2: 验证 lint 通过**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/profile.js
git commit -m "清理 profileService 非契约历史方法"
```

---

### Task 3: 清理 courseService 的 getCourseStudents 方法

**Files:**
- Modify: `src/api/services/course.js`

- [ ] **Step 1: 重新读取文件后，用最小 diff 仅删除 getCourseStudents**

先 Run：
```bash
cat /home/yezisama/workspace/workflow/EDUagent/frontend/src/api/services/course.js
```

然后仅删除以下方法块，保留其余所有代码不变：

删除第 7-9 行（含上方空行）：
```javascript
  getCourseStudents(courseId) {
    return apiClient.get(`/course/${courseId}/students`);
  },
```

- [ ] **Step 2: 验证 lint 通过**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/course.js
git commit -m "清理 courseService 错误学生列表封装"
```

---

### Task 4: 全量验证 — lint / build / E2E

**Files:** 无新建或修改（仅验证）

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

- [ ] **Step 3: 运行 E2E 测试（需要 Backend + Agent Service + MySQL duagent_test 在线）**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run test:e2e
```
Expected: 3/3 passed

> 如果 Backend/Agent 不在线，可以跳过此步骤，但需在 WORKFLOW.md 中标注 E2E 未重新运行。


---

### Task 5: 更新 WORKFLOW.md

**Files:**
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: 在 "最近验证" 末尾追加清理记录**

在 `frontend/WORKFLOW.md` 的 `## 最近验证` 部分的最后一条记录之后，追加：

```markdown
- 2026-06-05：清理阶段一遗留契约疑点 — 删除 `src/api/services/` 中 6 个未使用且不在 `Client-API.openapi.json` 声明中的方法：
  - `authService.logout` / `refreshToken` / `sendResetPasswordCode` / `resetPassword`
  - `profileService.updateProfile`
  - `courseService.getCourseStudents`
  - 清理后 `npm run lint` / `npm run build` 通过。
```

- [ ] **Step 2: 更新 "下一步建议" 为清理后的状态**

将 `## 下一步建议` 区块修改为：

```markdown
## 下一步建议

- 阶段一已发现的真实 API service 契约疑点已清理完毕。当前已删除的 6 个方法均无调用方且不在 `Client-API.openapi.json` 中，保留的 service 方法均有对应 OpenAPI 路径声明。
- 阶段二入口：以阶段二能力清单为输入，对照 `../docs/10-client-api/*` 逐项标注缺失字段、缺失接口和数据来源。
- 完成契约审查后，再决定是否修改 Client API、Backend Schema 或 Agent API。
```

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "记录阶段一契约疑点清理结果"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ 5 个 Task 覆盖了用户指定的全部 5 个清理步骤（确认未使用 → 删除/标记 → 验证 lint/build/e2e → 更新 WORKFLOW.md）。

**2. 无占位符：** ✅ 所有步骤都有完整代码和确切命令，无 TBD/TODO/"implement later"。

**3. 类型一致性：** ✅ 删除操作不涉及新类型/新函数签名，保留的方法签名与原始完全一致。

## 风险评估

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| 有隐藏调用方（动态 import、字符串反射等） | 极低 | 已用 `grep` 全文搜索确认：所有 6 个方法只在各自的定义文件中出现，0 处外部调用 |
| E2E 因环境不在线失败 | 中 | E2E 步骤标注为可跳过，lint + build 构成充分验证 |
| `npm run build` 因 tree-shaking 误报 warning | 极低 | 删除的是导出但未被引用的方法，打包器本就不会纳入 bundle |
