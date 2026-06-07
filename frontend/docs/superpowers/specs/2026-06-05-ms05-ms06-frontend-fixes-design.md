# MS-05 + MS-06 前端小适配设计

> 两个纯前端修复：加入课程入口 + 教师顶部身份展示。均不涉及 Backend/Agent/OpenAPI 改动。

**最后更新：** 2026-06-05

---

## 1. 目标

- **MS-05：** 学生端暴露"加入课程"入口，让 `POST /courses/join`（已有端点）可通过 UI 触达。
- **MS-06：** 教师端顶部不再硬编码身份信息，改为展示真实登录用户数据。

---

## 2. 范围与非目标

### 在范围

| 项 | 说明 |
|----|------|
| Navbar 课程选择区新增"+ 加入课程"按钮 | 学生端主入口 |
| 新增轻量 `JoinCourseDialog` 组件 | 邀请码输入 + 提交 + 状态反馈 |
| Dashboard 无课程状态补引导按钮 | 复用同一 Dialog |
| TeacherConsole 顶部身份改为真实 `useAuth` 数据 | 姓名/角色/文字头像 |
| lint + build + 手工 smoke | 验证 |

### 非目标

- 不新增 Client API 路径或字段
- 不修改 Backend 路由或 Agent 协议
- 不改造 Navbar 的整体下拉/选择器结构
- 不新增头像上传或图片存储能力
- 不修改 Navbar 用户下拉头像（那个硬编码 Google URL 是独立问题）

---

## 3. 契约依据

| 端 | 端点 | 状态 |
|----|------|------|
| `POST /courses/join` | 学生加入课程（course_code） | OpenAPI 已声明，Backend 已实现，`courseService.joinCourse` 已对齐 `{ course_code }`（`1161e43`） |
| `GET /users/me` | 当前用户信息 | 返回 `id, username, email, real_name, student_id, role, major, grade, guidance_level, created_at`。已在 AuthContext 的 `user` 对象中 |

---

## 4. UI 设计

### MS-05：加入课程入口

**Navbar（主入口）：**

当前 Navbar 第 30 行仅在 `courses.length > 0` 时渲染 `<select>` 课程切换器。修改为：

- 课程下拉区始终可见（不限于 `courses.length > 0`）
- Select 右侧追加一个 `+` 按钮
- 无课程时：select 隐藏，仅显示"+ 加入课程"文字按钮
- 有课程时：显示 select + 右侧小型 "+" 图标按钮

按钮位置约束：
- 若 select 可见，按钮在 select 同一行右侧
- 若 select 不可见（无课程），按钮在原本 select 位置

**Dashboard 无课程状态（辅助入口）：**

当前 Dashboard 第 83 行已有空状态：
```jsx
<FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />
```

下方追加一个"加入课程"按钮，点击打开同一 `JoinCourseDialog`。

**JoinCourseDialog：**

不引入外部组件库。使用项目已有 Tailwind 类体系。

状态：
- `open` — 弹窗是否可见
- `courseCode` — 输入值
- `submitting` — 提交中（禁用按钮）
- `error` — 错误信息
- `success` — 成功提示

交互流程：
```
点击 "+" 按钮 → open = true
→ 输入邀请码
→ 点击 "加入" → submitting = true, error = null
→ courseService.joinCourse(courseCode)
  → 成功（res.code === 200）：success = '加入成功' → refreshCourses()
    → 若返回数据含新课程 ID，切换到新课程
    → 1.5s 后关闭弹窗
  → 失败：error = res.message || '加入失败，请检查邀请码'
→ submitting = false
```

**注意：** `refreshCourses` 已由 `CourseContext` 公开导出（当前为 `refreshCourses: fetchCourses`），直接使用即可。

### MS-06：教师顶部身份展示

**当前硬编码（TeacherConsole.jsx 第 67-72 行）：**

```jsx
<div className="w-10 h-10 rounded-full bg-slate-200 overflow-hidden border border-outline-variant">
  <img alt="Teacher Profile" className="w-full h-full object-cover"
    src="https://lh3.googleusercontent.com/aida-public/AB6AXuBEmN6iPeykBJM4g-FxZGQKujWsCGE-ECZSb2n7Om_izFEwlflhnVLi8aiRkOPALKmOqmYspwDxQXhjRwpKinCsHeX82NYknLqB_BawjcrrG_R6fLceDe8E-djpgDunaUfMKNUpTMvJLEglTno8tbrwrX-u5ZbtloceQzZNyT3tUP1_YmA6sL8f0Py7ra53pu1vfMKFX-rn8TRIvfzsTB_Q-Pgp0_gVgYl-Cff4Cg2VxJf1eYU35oScr-WfgA0scltfK38DvdpCbyzX" />
</div>
<div className="flex flex-col">
  <span className="text-sm font-bold text-on-surface">Prof. Zhang</span>
  <span className="text-[10px] text-outline uppercase tracking-wider">系统管理员</span>
</div>
```

**替换为：**

```jsx
<div className="w-10 h-10 rounded-full bg-cyan-500/20 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-sm">
  {(user?.real_name || user?.username || '教').charAt(0)}
</div>
<div className="flex flex-col">
  <span className="text-sm font-bold text-on-surface">{user?.real_name || user?.username || '教师'}</span>
  <span className="text-[10px] text-outline uppercase tracking-wider">
    {roleLabelMap[user?.role] || '教师'}
  </span>
</div>
```

**需要 import：** `import { useAuth } from '../context/AuthContext';`，组件内 `const { user } = useAuth();`

**角色映射：**
```javascript
const roleLabelMap = { teacher: '教师', admin: '管理员' };
// 使用: roleLabelMap[user?.role] || '教师'
```
TeacherConsole 路由允许 `teacher` 和 `admin`，map 覆盖两者。不直接展示原始英文字段值。

---

## 5. 数据流

### MS-05

```
用户操作 → JoinCourseDialog 输入 courseCode
→ courseService.joinCourse(courseCode)
→ Backend POST /courses/join
→ 返回 { code, message, data: { id, name, teacher_name } }
→ 成功: await refreshCourses(); changeCourse(res.data.id)
→ Dialog 关闭
```

### MS-06

```
AuthContext.user（来自 GET /users/me）
→ useAuth() → { user }
→ TeacherConsole 读取 user.real_name, user.role
→ 渲染姓名/角色文字/首字头像
```

---

## 6. 文件改动

| `src/api/services/course.js` | 修改 | `joinCourse` 请求体 `{ invite_code }` → `{ course_code }`（与 OpenAPI JoinCourseRequest 对齐） |
| `src/components/Navbar.jsx` | 修改 | 课程选择区追加"+ 加入课程"按钮；无课程时展示按钮而非隐藏区域 |
| `src/components/JoinCourseDialog.jsx` | **新建** | 课程码输入弹窗（open/courseCode/submitting/error/success） |
| `src/context/CourseContext.jsx` | 修改 | 使用已有 `refreshCourses` 方法 |
| `src/pages/Dashboard.jsx` | 修改 | 无课程空状态追加"加入课程"按钮 |
| `src/pages/TeacherConsole.jsx` | 修改 | 导入 useAuth + roleLabelMap，替换硬编码姓名/角色/头像 |

---

## 7. 验证方式

| 方式 | 内容 |
|------|------|
| `npm run lint` | 零错误 |
| `npm run build` | 通过（允许已有 chunk size warning） |
| 手工：学生登录 | ① Navbar 课程选择器右侧有"+"按钮 → 点击弹出 Dialog → 输入邀请码 → 加入成功 → 课程列表刷新 ② 无课程时 Navbar 显示"+ 加入课程"文字按钮 |
| 手工：教师登录 | 顶部展示真实姓名（非 Prof. Zhang）和"教师"角色（非"系统管理员"），头像为真实姓名首字 |

---

## 8. 风险与降级

| 风险 | 概率 | 缓解 |
|------|------|------|
| `refreshCourses` 不存在于 CourseContext | 低（已确认） | 当前 `CourseContext.jsx` 已导出 `refreshCourses: fetchCourses`，直接使用即可 |
| `joinCourse` 返回不含新课程 ID | 低 | `POST /courses/join` 成功响应含 `data.id`，可直接 `changeCourse(res.data.id)` |
| 教师账号 role 值不是 `teacher` | 低 | 角色映射兜底：`user.role \|\| '教师'`，不直接展示原始 role 值 |
| 原生 select 难以在右侧放按钮 | 已确认 | 按钮放在 select 所在 `<div>` 内、select 之后，flexbox 即可 |

---

## 自审

1. **无占位符：** ✅ 无 TBD/TODO
2. **范围控制：** ✅ 仅 5 个文件，不碰 API/Backend/Agent
3. **歧义：** ✅ 入口位置、Dialog 状态、数据映射均已明确
