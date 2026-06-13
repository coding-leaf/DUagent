# 学生画像学习档案展示设计

## 背景

个人资料页已经接入 `GET /profile`、`POST /profile/dialogue-update`、`POST /profile/refresh` 和 `GET /tasks/{task_id}`，可以读取、补充和静默同步学生课程画像。

当前问题不在链路，而在展示语义：页面会把后端画像维度和枚举值按系统字段直出，例如 `daily_homework` 被放在“学习目标”下展示为“每日作业”，`discipline.subject` 可能展示课程 ID。这类文案更像后台特征表，不适合作为学生个人资料页。

## 目标

把个人资料页的画像区域从“系统画像字段”调整为“学习档案”口径，使学生能直接理解每个维度的含义，同时保留比赛题要求的六维画像表达。

本次只调整前端展示命名和格式化，不改后端字段、不改 OpenAPI、不改存储结构。

## 展示命名

| 接口维度 key | 新展示名 | 展示说明 |
| --- | --- | --- |
| `learning_goal` | 当前学习方向 | 当前阶段主要学习场景或方向，不表达为最终目标 |
| `weak_points` | 待提升内容 | 来自错题、评测或个人补充的薄弱知识点 |
| `resource_preference` | 学习资料偏好 | 学生更适合或更常使用的资料类型 |
| `guidance_level` | 辅导方式 | AI 介入和提示的方式 |
| `knowledge_progress` | 掌握进度 | 当前课程知识掌握情况 |
| `discipline` | 学习习惯 | 连续学习、活跃度和学习稳定性 |

页面标题建议从“六维画像”调整为“学习档案”，说明文案保持克制，例如“根据学习行为、评测结果和个人补充生成的课程学习档案。”

## 枚举展示

### 当前学习方向

| 原值 | 展示值 |
| --- | --- |
| `daily_homework` | 课后巩固 |
| `exam_sprint` | 备考冲刺 |
| `casual` | 兴趣拓展 |

### 学习资料偏好

| 原值 | 展示值 |
| --- | --- |
| `code_practice` | 代码实操 |
| `text_analysis` | 文本解析 |
| `chart_logic` | 图表逻辑 |
| `video_animation` | 视频动画 |
| `formula_derivation` | 公式推导 |

### 辅导方式

| 原值 | 展示值 |
| --- | --- |
| `L1` | 启发点拨 |
| `L2` | 分步伴学 |
| `L3` | 详细讲解 |

引导粒度调节卡片可以继续保留 `L1/L2/L3`，但学习档案摘要中只展示面向学生的辅导方式。

### 学习习惯

| 原值 | 展示值 |
| --- | --- |
| `starter` | 入门起步 |
| `active` | 稳定学习 |
| `focused` | 高频投入 |

`discipline.subject` 如果是当前课程 ID，展示当前课程名；如果能在课程列表中匹配到课程名，也展示课程名；如果仍是不可识别的 ID，则不展示该字段。

## 来源标签

| 原来源 | 新展示 |
| --- | --- |
| `system_profile` | 系统分析 |
| `system_pending` | 数据不足 |
| `resource_usage` | 学习行为 |
| `evaluation` | 评测结果 |
| `activity` | 学习记录 |
| `profile_dialogue` | 个人补充 |

## 空值文案

| 维度 | 空值展示 |
| --- | --- |
| 待提升内容 | 暂无错题或评测记录 |
| 掌握进度 | 暂无评测记录 |
| 学习习惯 | 暂无连续学习记录 |
| 其他维度 | 待补充 |

## 数据流

1. 页面继续通过 `profileService.getStudentProfile(activeCourseId)` 获取画像。
2. 前端使用 `profile_dimensions[].key` 决定展示名和格式化方式。
3. `profile_dimensions[].label` 作为后端原始标签保留但不优先展示。
4. 刷新画像仍通过 `profileService.refreshProfile(activeCourseId)` 创建任务，轮询 `taskService.getTaskStatus(taskId)`，完成后重新拉取画像。
5. 对话补充仍通过 `profileService.updateProfileByDialogue(activeCourseId, message)` 合并画像。

## 错误处理

本次不改变现有错误处理。画像刷新失败、任务查询失败、画像加载失败仍沿用当前页面提示。

格式化层遇到未知枚举时保留原值展示，避免新增后端枚举导致页面空白；但不可识别的课程 ID 不直接展示。

## 测试

实现后运行：

```bash
npm run lint
npm run build
```

人工验证重点：

- `daily_homework` 展示为“课后巩固”，不再出现在“学习目标”下。
- 学习档案第一维展示为“当前学习方向”。
- `resource_preference` 展示为中文资料类型。
- `guidance_level` 摘要展示为“启发点拨 / 分步伴学 / 详细讲解”。
- `discipline` 不展示裸课程 ID。

## 非目标

- 不修改 Backend / Agent 画像结构。
- 不修改 OpenAPI。
- 不新增画像维度。
- 不调整画像生成提示词。
- 不重做个人资料页整体视觉布局。
