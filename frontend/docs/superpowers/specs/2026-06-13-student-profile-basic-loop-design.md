# Student Profile Basic Loop Design

## 背景

软件杯 A3 赛题把“对话式学习画像自主构建”列为核心功能：系统应通过自然语言对话，结合学生专业、学习目标、学习历史等信息，自动抽取特征，构建不少于 6 个维度的动态学生画像，并支持随学随新。

当前项目已有 `StudentProfile.jsx`、`GET /profile`、`/profile/refresh`、Quiz、LearningPath、Evaluation、AIChat 等基础能力，但画像能力对用户不够显性：学生看不到画像如何产生、哪些维度已形成、哪些数据仍待积累，也缺少一个轻量的自然语言补充入口。

本设计目标是补齐“基础功能闭环”，不做复杂推荐系统，不引入 mock 数据，不重构长期记忆。

## 目标

第一版把学生画像做成可演示、可持久化、可解释的最小闭环：

1. 学生能在 `StudentProfile` 页面看到 6 个画像维度。
2. 学生能用一句自然语言补充画像。
3. 系统能抽取结构化字段并持久化。
4. 页面能展示每个维度的数据来源。
5. 没有真实数据的维度显示“待积累”，不造假。
6. 第一版不直接影响 LearningPath 排序或资源推荐算法。

## 画像维度

| 维度 | 含义 | 优先数据来源 | 空态 |
| --- | --- | --- | --- |
| 知识基础 | 当前课程知识掌握基础 | Quiz 正确率、Evaluation、LearningPath 节点状态 | 待通过练习积累 |
| 薄弱知识点 | 容易出错或未掌握的知识点 | Quiz 错题、Evaluation weak_points、AIChat 对话抽取 | 待通过练习或对话识别 |
| 学习目标 | 学生当前学习目的 | 自然语言补充画像 | 待补充 |
| 学习偏好 | 学生偏好的学习方式 | 自然语言补充画像、AIChat 对话 | 待补充 |
| 资源偏好 | 文档、图解、代码、题目等资源偏好 | 资源使用统计；第一版可为空 | 待使用资源后积累 |
| 学习驱动 / 节奏 | 日常学习、考前突击、项目实践等驱动 | 自然语言补充画像、近期学习行为统计 | 待补充 |

字段命名应尽量贴近现有 `UserProfile` 中的语义字段，例如 `knowledge_coordinates`、`cognitive_blindspots`、`modal_preference`、`drive_intent`。如果现有字段不足，第一版优先把自然语言补充结果写入 `UserProfile.modal_preference` / `drive_intent` / `cognitive_blindspots` 等 JSON 字段，不新增数据库表。

## 用户体验

`StudentProfile` 页面保留现有基础资料和指导级别能力，新增“学习画像”区域：

- 展示 6 张画像卡片，每张卡片包含维度名称、当前结论、来源说明。
- 来源说明使用固定枚举：`profile_dialogue`、`quiz_result`、`evaluation`、`resource_usage`、`system_pending`。
- 空态展示“待积累”，并给出下一步提示，例如“完成一次节点练习后可识别薄弱知识点”。

新增“补充画像”输入区：

```text
我正在学 C 语言指针，准备期末考试，喜欢代码例子和图解，不太理解动态内存分配。
```

提交后系统抽取：

```json
{
  "learning_goal": "准备期末考试，重点学习 C 语言指针",
  "learning_preferences": ["代码例子", "图解"],
  "weak_points": ["动态内存分配"],
  "drive_intent": "exam_cram"
}
```

页面刷新后不丢失，并在对应画像卡片显示来源为“对话补充”。

## 接口设计

优先复用现有 `GET /profile` 展示画像。

新增一个最小画像补充接口：

```http
POST /api/v1/profile/dialogue-update
```

请求：

```json
{
  "course_id": "当前教学班 id",
  "message": "我正在学 C 语言指针，准备期末考试，喜欢代码例子和图解，不太理解动态内存分配。"
}
```

响应：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "profile": {
      "learning_goal": "准备期末考试，重点学习 C 语言指针",
      "learning_preferences": ["代码例子", "图解"],
      "weak_points": ["动态内存分配"],
      "drive_intent": "exam_cram"
    },
    "sources": {
      "learning_goal": "profile_dialogue",
      "learning_preferences": "profile_dialogue",
      "weak_points": "profile_dialogue",
      "drive_intent": "profile_dialogue"
    }
  }
}
```

Backend 负责：

1. 校验学生对 `course_id` 有访问权限。
2. 调 Agent 或本地 LLM 抽取结构化画像字段。
3. 合并到当前 `UserProfile`。
4. 返回合并后的画像摘要。

Agent 抽取失败时，接口返回明确错误，不写入空画像；前端显示失败提示。

## 数据合并规则

第一版采用保守合并：

- 对话补充的 `learning_goal` 覆盖旧的对话补充目标，但不覆盖系统评估产生的知识掌握数据。
- `learning_preferences`、`weak_points` 使用去重追加，最多保留 10 条。
- `drive_intent` 可由对话补充覆盖。
- Quiz / Evaluation 产生的薄弱点优先级高于对话自述，但两者都可展示，来源不同。
- 没有来源的数据不展示为结论。

## 不做范围

第一版明确不做：

- 不改变 LearningPath 排序。
- 不改变资源推荐算法。
- 不做心理测评或复杂学习风格量表。
- 不做画像分数和权重模型。
- 不新增长期记忆系统。
- 不用前端 mock 数据填充画像。
- 不生成视频、PPT 或 OJ 题。

这些能力可以作为比赛增强项，但不进入基础功能闭环。

## 验收标准

1. 学生进入 `StudentProfile` 能看到 6 个画像维度。
2. 未产生数据的维度显示“待积累”，不是空白或假结论。
3. 学生提交自然语言画像补充后，对应维度更新并持久化。
4. 刷新页面后画像结果仍存在。
5. 至少一个维度能展示来自 Quiz / Evaluation 的真实来源。
6. 至少一个维度能展示来自自然语言补充的真实来源。
7. Agent 抽取失败时不写入错误画像，前端展示失败提示。
8. 不发生 OpenAPI 静默漂移；新增接口需要同步 Client API 文档。

## 实施顺序建议

1. 后端新增 `POST /profile/dialogue-update`，先用可测试的抽取服务接口封装 Agent 调用。
2. 扩展 `GET /profile` 响应或前端适配已有字段，统一生成 6 维展示模型。
3. 前端 `StudentProfile.jsx` 新增画像卡片和补充输入区。
4. 补充 OpenAPI / 前端接口规范。
5. 跑 Backend profile 测试、Frontend lint/build，并做一次学生端手工验收。
