# StudentProfile 真实字段接线设计

> 纯前端适配：将页面从幽灵字段模型切回真实契约。Backend/OpenAPI/Agent 零改动。

**最后更新：** 2026-06-06

---

## 1. 目标

StudentProfile.jsx 当前读取的字段几乎全部不在契约中（`name`、`level`、`title`、`current_course`、`system_suggestion`、`knowledge_nodes`、`weekly_max_accuracy`、`total_duration_hours`），而 Backend 已返回的真实数据（`modal_preference`、`guidance_level`、`knowledge_coordinates`、`cognitive_blindspots`、`drive_intent`、`discipline_badge`）完全未消费。

本设计的目标是把页面重新接回真实契约字段，删除幽灵字段消费和假图形展示。

---

## 2. 范围与非目标

### 在范围

- StudentProfile.jsx：5 张卡片重新接线到真实数据
- 引入 `useAuth()` 获取真实姓名/角色
- 从 `useCourse()` 获取当前课程名（已有方法）
- 修复 `!activeCourseId` 时无限 loading 的已有 bug，替换为空态页面
- 删除当前 7 个幽灵字段的解构和使用
- 删除"学习热度与准度"整张卡片（完全建立在静态 SVG + 不存在字段上）

### 非目标

- 不新增 Client API 路径或字段
- 不修改 Backend 路由或 Agent 协议
- 不修改 OpenAPI 契约
- 不新增组件文件（仅改动 StudentProfile.jsx）
- 不引入新依赖

---

## 3. 契约依据

| 层次 | 文件/端点 | 关键字段 |
|------|----------|---------|
| Auth | `GET /users/me`（useAuth().user） | `real_name`, `username`, `role` — 姓名按 `real_name \|\| username` 优先级取值 |
| Course | `useCourse()` | `courses[]`（每项含 `id`, `name`），`activeCourseId` |
| Profile | `GET /profile?course_id=` | `modal_preference`, `guidance_level`, `knowledge_coordinates[]`, `cognitive_blindspots[]`, `drive_intent`, `discipline_badge`, `generated_at` |
| Evaluation | `GET /evaluation?course_id=` | `progress_table`, `mastery_table`, `resource_usage_table`, `summary_text`, `generated_at`（**当前页面不消费；实施后检查是否可移除调用**） |

---

## 4. 卡片方案（5 张）

### 卡片 1：个人信息

**旧数据源：** `profileData.name` → `profileData.level` + `profileData.title` → `profileData.current_course`

**新数据源：**

| 展示内容 | 数据源 | 兜底 |
|---------|--------|------|
| 头像首字 | `useAuth().user` 按 `real_name \|\| username \|\| "学"` 取首字 | `"学"` |
| 姓名 | `useAuth().user` 按 `real_name \|\| username \|\| "学生"` 取值 | `"学生"` |
| 当前课程 | `useCourse().courses` 按 `activeCourseId` 查找 `name` | `"未选择"` |
| 勋章等级 | `profile.discipline_badge.level` | `"—"` |
| 擅长学科 | `profile.discipline_badge.subject` | `"—"` |

**语义限定：** `discipline_badge.level` 和 `discipline_badge.subject` **仅表学科勋章**，不包装为通用用户等级体系或通用称号。展示文案为"学科勋章：{subject} · {level}"。

### 卡片 2：模态偏好

**旧：** 占位文字 "模态偏好数据待 Backend 返回"

**新：** `profile.modal_preference` 5 个维度，每维度一条进度条（0-100）

| 维度 | 字段 | 中文标签 |
|------|------|---------|
| video_animation | `modal_preference.video_animation` | 视频动画 |
| chart_logic | `modal_preference.chart_logic` | 图表逻辑 |
| text_analysis | `modal_preference.text_analysis` | 文本分析 |
| code_practice | `modal_preference.code_practice` | 代码实操 |
| formula_derivation | `modal_preference.formula_derivation` | 公式推导 |

进度条颜色按数值阶梯：低值灰 → 高值青。不做饼图。

### 卡片 3：引导粒度

**旧：** 硬编码 50% 进度条 + 静态 L2 高亮

**新：** 从 `profile.guidance_level` 取值

| 展示内容 | 数据源 | 说明 |
|---------|--------|------|
| 当前等级 | `guidance_level.current`（L1/L2/L3） | 高亮对应刻度点 |
| 进度条位置 | L1 → 33%，L2 → 66%，L3 → 100% | 计算值，非后端返回 |
| 更新时间 | `guidance_level.updated_at` | 相对时间展示（"X 天前更新"）|
| L1/L2/L3 描述文案 | 组件内常量 | 保持现有中文描述不变 |
| 系统建议 | **删除**（`system_suggestion` 不存在于契约） | — |

### 卡片 4：知识坐标 + 认知盲区（合并卡片）

**旧：** 单独卡片 `knowledge_nodes`（4 种状态：mastered/familiar/weak/blind_spot）

**新：** 上半区域 `knowledge_coordinates[]`，下半区域 `cognitive_blindspots[]`，均为列表。

**上半 — 知识坐标（`knowledge_coordinates[]`）：**

status 只有两种值：`mastered`（绿色标签"已掌握"）和 `learning`（琥珀色标签"学习中"）。

每行格式：`[彩色标签] 知识点名称`，有 `mastered_at` 时追加"· XX 天前掌握"。

| status 值 | 标签色 | 标签文字 |
|-----------|--------|---------|
| `mastered` | 绿色 | 已掌握 |
| `learning` | 琥珀/黄 | 学习中 |

**下半 — 认知盲区（`cognitive_blindspots[]`）：**

| severity 值 | 严重度标签 |
|-------------|-----------|
| `high` | 高（红色） |
| `medium` | 中（琥珀） |
| `low` | 低（灰色） |

每行格式：`[严重度标签] 盲区名称 · 错误 {error_count} 次`

**禁止：** 不画节点图、连线、雷达图、饼图、SVG 折线。直接标签+文字列表渲染。

### 卡片 5：驱动力 + 学科勋章（新建卡片）

**旧：** "学习热度与准度"卡片 — 静态 SVG 折线图 + 幽灵字段 `weekly_max_accuracy`、`total_duration_hours`

**删除旧卡片全部内容。**

**新：** 两个轻量数据源合并到一张卡片。

**驱动力（`drive_intent`）：**

| 字段 | 展示 |
|------|------|
| `type` | 中文映射：`exam_sprint` → "备考冲刺"，`daily_homework` → "日常作业"，`casual` → "兴趣驱动" |
| `intensity` | 0-100 强度进度条 |

**学科勋章（`discipline_badge`）：**

| 字段 | 展示 |
|------|------|
| `subject` | 学科名 |
| `level` | 勋章等级标签 |
| `streak_days` | 连续打卡 X 天 |

---

## 5. 数据流

```
useEffect(activeCourseId)
├── !activeCourseId → 渲染空态页面（标题 + 说明 + "去课程页"按钮），停止 loading
├── GET /profile?course_id= → profile（卡片 2、3、4、5）
├── useAuth().user          → real_name || username || 兜底（卡片 1）
└── useCourse()             → courses、activeCourseId（卡片 1 课程名）
```

**关于 GET /evaluation：**

当前代码在 `useEffect` 中并行调用 `getLearningEffects(activeCourseId)` → `GET /evaluation`，并将返回数据解构为 `effectsData`。实施完成后，检查 StudentProfile 组件是否在任何地方消费 evaluation 的返回值：

- 检查范围包括 `effectsData` 的 state 声明、`useEffect` 中的 `Promise.all`、解构赋值、JSX 引用、以及因不再需要而可能残留的 error/loading 分支
- 若 5 张卡片均不再依赖 evaluation 的任何字段 → 删除该 API 调用、effectsData state、解构代码及相关分支
- 若 evaluation 数据被任何卡片（如 knowledge_coordinates 回退展示）间接使用 → 保留调用
- 判定标准：以**组件是否还在任何地方消费 evaluation 返回值**为准（不仅仅是 JSX），不预先假设

---

## 6. 文件改动

| 文件 | 改动 | 说明 |
|------|------|------|
| `src/pages/StudentProfile.jsx` | **仅改此文件** | 重接 5 卡片数据源，删除幽灵字段解构和旧卡片 5 |

不加新文件，不动 service 层，不动 context 层。

---

## 7. 无课程空态页面

当前代码在 `!activeCourseId` 时 `useEffect` 直接 `return`（不执行 API 调用），但 `loading` 保持 `true`（初始值），导致页面永久显示 spinner。这是一个已有 bug。

### 修复方式

`useEffect` 中：`!activeCourseId` 时显式 `setLoading(false)` 后 `return`。

组件渲染：在 `loading` 检查之前，先判断 `!activeCourseId`，渲染空态页面。

### 空态内容

- **标题：** "还没有可查看的课程画像"
- **说明：** "加入一门课程后，这里会展示你的模态偏好、引导粒度、知识坐标和学习状态。"
- **操作按钮：** "去课程页"（`navigate('/dashboard')`），单个按钮，不再加"去加入课程"（加入入口已在 Dashboard 页面内）

### 渲染顺序

```
activeCourseId 不存在？
  → 是：渲染空态页面（标题 + 说明 + 按钮）
  → 否，loading？
    → 是：渲染 spinner
    → 否：渲染 5 张卡片
```

---

## 8. 空态处理

| 场景 | 处理 |
|------|------|
| `!activeCourseId` | 渲染空态页面替代 loading spinner：标题"还没有可查看的课程画像"，说明"加入一门课程后，这里会展示你的模态偏好、引导粒度、知识坐标和学习状态。"，操作按钮"去课程页"（跳转 `/dashboard`）。`useEffect` 中 `!activeCourseId` 时直接 `setLoading(false)` 后 return，避免无限加载。 |
| `activeCourseId` 存在但 `profile === null`（API 失败） | 所有卡片显示兜底文案，不崩溃 |
| `modal_preference` 所有维度 = 默认 50 | 正常展示（默认值来自后端 `_default_profile`） |
| `knowledge_coordinates` 空数组 `[]` | 知识坐标区显示空态文案"暂无知识坐标数据" |
| `cognitive_blindspots` 空数组 `[]` | 盲区显示空态文案"暂无认知盲区记录" |
| `drive_intent` 默认值 `{type:"casual", intensity:30}` | 正常展示 |
| `discipline_badge` 三个字段全为空/默认 | 卡片 1 勋章位显示 `"—"`，卡片 5 勋章区显示空态文案 |
| `guidance_level` 为默认 `L2`、`updated_at` 为空字符串 | 展示 L2 但不显示更新时间（`updated_at` 为空时隐藏） |

---

## 9. 验证方式

| 方式 | 内容 |
|------|------|
| `npm run lint` | 零错误 |
| `npm run build` | 通过（允许已有 chunk size warning） |
| 手工 smoke：无课程 | 学生登录但未加入任何课程 → Profile 页面：展示空态（标题+说明+按钮），不无限转圈 |
| 手工 smoke：有课程 | 学生登录 → 选择课程 → Profile 页面：5 张卡片展示真实数据，无占位文字、无硬编码 50%、无静态 SVG 图 |
| 手工 smoke：空 profile | 新用户（无 profile 行时 Backend 返回默认值）：所有卡片展示默认值或空态文案，不崩溃 |

---

## 10. 风险与降级

| 风险 | 概率 | 缓解 |
|------|------|------|
| `useAuth().user` 为 null（未登录状态） | 低 | ProtectedRoute 已守卫，`user` 必定有值；仍做 `?.` 兜底 |
| `useCourse().courses` 为空数组 | 中 | 课程名显示"未选择" |
| `discipline_badge` 字段为空对象（默认值 `{subject:"", level:"", streak_days:0}`） | 中 | 卡片 1 勋章位显示 `"—"`；卡片 5 勋章区显示空态文案 |
| `guidance_level.current` 为不预期值 | 低 | 进度条兜底 50%，映射表兜底"未知" |
| `knowledge_coordinates.status` 为 `mastered`/`learning` 以外的值 | 低 | 兜底标签为灰色"未知" |
| `cognitive_blindspots.severity` 为 `high`/`medium`/`low` 以外的值 | 低 | 兜底标签为灰色 |
| `drive_intent.type` 为不预期值 | 低 | 中文映射表兜底直接展示原始值 |

---

## 自审

1. **无占位符：** ✓ 无 TBD/TODO
2. **范围控制：** ✓ 仅改 `StudentProfile.jsx`，不碰 API/Backend/Agent/OpenAPI
3. **歧义：** ✓ 每张卡片的数据源、展示形式、空态均已明确
4. **语义限定：** ✓ discipline_badge 仅作学科勋章，不包装为通用等级体系
5. **evaluation 调用：** ✓ 不预先判定移除，检查范围为组件任何地方是否消费 evaluation 返回值
6. **无课程空态：** ✓ `!activeCourseId` 改为空态页面（标题+说明+按钮），消除无限 loading bug
7. **姓名兜底：** ✓ 优先级 `real_name || username || "学生"`，头像首字同步
