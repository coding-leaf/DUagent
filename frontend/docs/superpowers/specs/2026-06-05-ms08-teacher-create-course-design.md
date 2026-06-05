# MS-08 教师创建课程入口设计

> 纯前端修复：暴露已有 `POST /courses` 端点的 UI 入口。与 MS-05（学生加入课程）镜像。

**最后更新：** 2026-06-05

---

## 1. 目标

教师端暴露"创建课程"入口，让 `POST /courses`（已有端点）可通过 UI 触达，创建成功后展示课程码供学生加入。

## 2. 范围与非目标

### 在范围

- TeacherConsole 顶部或班级选择区加"创建课程"按钮
- 新建 `CreateCourseDialog.jsx`（输入课程名称 → 调用 API → 展示课程码）
- 无班级空状态加创建入口
- 成功后刷新 `getClasses`（课程/班级列表）

### 非目标

- 不新增 API
- 不修改 Backend/Agent
- 不创建课程编辑/删除功能

## 3. 契约依据

| 端点 | 说明 |
|------|------|
| `POST /courses` | 请求 `{ name, description? }`，返回 `{ code: 201, data: { id, name, course_code } }`，需要 teacher 角色 |
| `courseService.createCourse(data)` | 已封装，无调用方 |

## 4. UI 设计

**TeacherConsole 入口：**

在顶部导航区（身份展示块右侧或班级 select 旁）加"创建课程"按钮。模式参考 Navbar MS-05 的"+"按钮。

**CreateCourseDialog：**

状态：`open` / `name` / `description` / `submitting` / `error` / `created`（含返回的 `course_code`）

交互：
```
点击"创建课程" → Dialog 打开 → 输入课程名称
→ 提交 → POST /courses { name, description? }
→ 成功 → 展示课程码 + "复制课程码"按钮
→ 关闭后刷新 teachingService.getClasses()
```

**无班级空状态：**

TeacherConsole 无班级时同样展示创建入口按钮。

## 5. 数据流

```
CreateCourseDialog → courseService.createCourse({ name, description })
→ Backend POST /courses → 返回 { id, name, course_code }
→ 展示课程码供教师复制给学生
→ 关闭 Dialog → refreshClasses() → 列表更新
```

## 6. 文件改动

| 文件 | 操作 |
|------|------|
| `src/components/CreateCourseDialog.jsx` | 新建 |
| `src/pages/TeacherConsole.jsx` | 加"创建课程"按钮 + 导入 Dialog + 接入 refreshClasses |

## 7. 验证

- `npm run lint` / `npm run build`
- 手工：教师登录 → 创建课程 → 看到课程码 → 关闭 → 列表刷新
- 手工：学生用课程码通过 Navbar "+ 加入课程"加入 → 成功
- 无 OpenAPI/契约漂移

## 自审

- 无占位符 ✅
- 范围受控：2 文件 ✅
- 契约无变更 ✅
