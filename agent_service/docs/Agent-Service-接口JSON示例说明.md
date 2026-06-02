# Agent Service 接口 JSON 示例说明

> 用途：给前后端联调、Apifox Mock 直接使用。
>
> 约束：
> - 以 `docs/20-agent-api/Agent-Service.openapi.json` 为准
> - 所有 JSON 示例均为可直接复制的标准 JSON
> - 同步接口统一返回 `{ "code": 200, "message": "success", "data": ... }`
> - 异步资源接口返回 `202 accepted`

## 1. 健康检查

### 接口

`GET /agent/v1/health`

### 请求示例

无请求 Body。

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "healthy",
    "qdrant_connected": true,
    "model_loaded": true,
    "model_name": "deepseek-chat",
    "uptime_seconds": 86400
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| code | integer | 业务状态码，成功时为 200 |
| message | string | 业务消息，成功时为 `success` |
| data.status | string | 服务状态，`healthy / degraded / unhealthy` |
| data.qdrant_connected | boolean | Qdrant 连接状态 |
| data.model_loaded | boolean | 大模型是否已加载 |
| data.model_name | string | 当前加载模型名称 |
| data.uptime_seconds | integer | 服务运行时长，单位秒 |

---

## 2. 智能辅导对话

### 接口

`POST /agent/v1/tutoring/chat`

### 请求示例

```json
{
  "user_id": "user_001",
  "scope": "course",
  "course_id": "course_ds_c",
  "conversation_id": "conv_20260527_001",
  "message": "请用一个简单例子解释栈和队列的区别",
  "user_profile": {
    "guidance_level": "L2",
    "modal_preference": {
      "video_animation": 70,
      "chart_logic": 88,
      "text_analysis": 65,
      "code_practice": 72,
      "formula_derivation": 30
    },
    "knowledge_mastered": [
      "顺序表",
      "链表"
    ],
    "knowledge_weak": [
      "栈",
      "队列"
    ]
  },
  "conversation_summary": "用户前面已经理解了顺序表和链表，但对线性结构的受限操作还不熟悉。",
  "recent_messages": [
    {
      "role": "user",
      "content": "链表我大概懂了",
      "meta": {
        "message_id": "msg_u_001"
      }
    },
    {
      "role": "assistant",
      "content": "很好，我们接下来可以看栈和队列。",
      "meta": {
        "message_id": "msg_a_001"
      }
    }
  ]
}
```

### SSE 响应事件示例

Apifox Mock 建议按单条事件分别维护。

`chunk`
```json
{
  "type": "chunk",
  "content": "栈和队列的核心区别在于元素取出的顺序不同。"
}
```

`diagram`
```json
{
  "type": "diagram",
  "data": "graph TD\nA[入栈 push] --> B[栈顶 top]\nC[入队 enqueue] --> D[队头 front]"
}
```

`knowledge_points`
```json
{
  "type": "knowledge_points",
  "data": [
    {
      "name": "栈",
      "chapter": "线性表扩展结构",
      "mastery": 45
    },
    {
      "name": "队列",
      "chapter": "线性表扩展结构",
      "mastery": 40
    }
  ]
}
```

`suggestion`
```json
{
  "type": "suggestion",
  "data": {
    "tips": [
      "先记住栈是后进先出",
      "再记住队列是先进先出"
    ],
    "similar_exercises": [
      "判断表达式求值更适合用栈还是队列",
      "分析打印任务调度为何更像队列"
    ]
  }
}
```

`done`
```json
{
  "type": "done",
  "message_id": "msg_agent_20260527_001",
  "knowledge_points_used": [
    "栈",
    "队列"
  ],
  "suggested_exercises": [
    "用生活中的场景分别举出一个栈和队列的例子"
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| scope | string | 对话范围，`course / global`，默认 `course` |
| course_id | string | 课程 ID，`scope=course` 时必填 |
| conversation_id | string | 对话 ID，继续已有对话时传入 |
| message | string | 用户当前消息 |
| user_profile | object | Backend 组装的用户画像 |
| user_profile.guidance_level | string | 引导粒度，`L1 / L2 / L3` |
| user_profile.modal_preference | object | 用户模态偏好 |
| user_profile.knowledge_mastered | array[string] | 已掌握知识点名称列表 |
| user_profile.knowledge_weak | array[string] | 薄弱知识点名称列表 |
| conversation_summary | string | 对话压缩后的全局摘要 |
| recent_messages | array | 最近 N 轮消息缓冲 |
| recent_messages[].role | string | `user / assistant` |
| recent_messages[].content | string | 消息内容 |
| recent_messages[].meta | object | 消息元信息 |
| SSE.type | string | 事件类型，`chunk / diagram / knowledge_points / suggestion / done` |

---

## 3. 生成/刷新用户画像

### 接口

`POST /agent/v1/profile/generate`

### 请求示例

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "evaluation_data": {
    "progress": {
      "completed_chapters": 3,
      "total_chapters": 8
    },
    "mastery": {
      "average_score": 76
    },
    "resource_usage": {
      "document": 5,
      "video": 2,
      "code": 3
    }
  },
  "quiz_history": [
    {
      "score": 80,
      "chapter": "线性表",
      "created_at": "2026-05-26T10:00:00Z"
    },
    {
      "score": 68,
      "chapter": "栈与队列",
      "created_at": "2026-05-27T08:30:00Z"
    }
  ],
  "resource_usage_stats": {
    "video_count": 2,
    "document_count": 5,
    "code_count": 3,
    "quiz_count": 6
  },
  "drive_intent_data": {
    "recent_7d_sessions": 5,
    "recent_7d_duration": 210
  }
}
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "modal_preference": {
      "video_animation": 62,
      "chart_logic": 85,
      "text_analysis": 73,
      "code_practice": 78,
      "formula_derivation": 35
    },
    "guidance_level_suggestion": {
      "recommended": "L2",
      "reason": "用户具备基础理解能力，但在薄弱知识点上仍需要阶段性提示。"
    },
    "knowledge_coordinates": [
      {
        "name": "顺序表",
        "status": "mastered"
      },
      {
        "name": "栈",
        "status": "learning"
      }
    ],
    "cognitive_blindspots": [
      {
        "name": "队列",
        "error_count": 3,
        "severity": "medium"
      }
    ],
    "drive_intent": {
      "type": "daily_homework",
      "intensity": 72
    },
    "discipline_badge": {
      "subject": "数据结构",
      "level": "bronze",
      "streak_days": 6
    }
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| course_id | string | 课程 ID |
| evaluation_data | object | 最新学习效果评估 |
| quiz_history | array | 练习历史记录 |
| quiz_history[].score | number | 正确率 |
| quiz_history[].chapter | string | 章节 |
| quiz_history[].created_at | string | 完成时间，建议 ISO 8601 |
| resource_usage_stats | object | 各类学习资源使用统计 |
| drive_intent_data | object | 近期学习频率数据 |
| data.modal_preference | object | 五维模态偏好雷达图 |
| data.guidance_level_suggestion | object | 建议的引导等级及原因 |
| data.knowledge_coordinates | array | 知识坐标标签 |
| data.cognitive_blindspots | array | 认知盲区标签 |
| data.drive_intent | object | 学习驱动类型和强度 |
| data.discipline_badge | object | 学科底座徽章信息 |

---

## 4. 生成学习效果评估

### 接口

`POST /agent/v1/evaluation/generate`

### 请求示例

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "learning_progress": {
    "chapter_progress": [
      {
        "chapter": "线性表",
        "completion_rate": 100,
        "time_spent": 120
      },
      {
        "chapter": "栈与队列",
        "completion_rate": 65,
        "time_spent": 90
      }
    ]
  },
  "quiz_results": [
    {
      "chapter": "线性表",
      "score": 85,
      "created_at": "2026-05-25T09:00:00Z"
    },
    {
      "chapter": "栈与队列",
      "score": 68,
      "created_at": "2026-05-27T09:30:00Z"
    }
  ],
  "resource_usage": {
    "by_type": {
      "document": 5,
      "mindmap": 1,
      "reading": 2,
      "code": 3,
      "video": 1
    },
    "by_chapter": {
      "线性表": 6,
      "栈与队列": 6
    }
  }
}
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "progress_table": {
      "columns": [
        {
          "key": "chapter",
          "title": "章节"
        },
        {
          "key": "completion_rate",
          "title": "完成率"
        },
        {
          "key": "time_spent",
          "title": "学习时长"
        }
      ],
      "rows": [
        {
          "chapter": "线性表",
          "completion_rate": 100,
          "time_spent": 120
        },
        {
          "chapter": "栈与队列",
          "completion_rate": 65,
          "time_spent": 90
        }
      ]
    },
    "mastery_table": {
      "columns": [
        {
          "key": "knowledge_point",
          "title": "知识点"
        },
        {
          "key": "mastery",
          "title": "掌握度"
        }
      ],
      "rows": [
        {
          "knowledge_point": "顺序表",
          "mastery": 88
        },
        {
          "knowledge_point": "栈",
          "mastery": 61
        }
      ]
    },
    "resource_usage_table": {
      "columns": [
        {
          "key": "resource_type",
          "title": "资源类型"
        },
        {
          "key": "count",
          "title": "使用次数"
        }
      ],
      "rows": [
        {
          "resource_type": "document",
          "count": 5
        },
        {
          "resource_type": "code",
          "count": 3
        }
      ]
    },
    "summary_text": "用户在线性表部分基础较稳，但在栈与队列的理解和迁移应用上仍有明显提升空间。"
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| course_id | string | 课程 ID |
| learning_progress | object | 学习进度统计 |
| learning_progress.chapter_progress | array | 各章节完成度列表 |
| quiz_results | array | 各次练习结果汇总 |
| resource_usage | object | 资源使用统计 |
| resource_usage.by_type | object | 各资源类型使用次数 |
| resource_usage.by_chapter | object | 各章节资源使用分布 |
| data.progress_table | object | 学习进度表 |
| data.mastery_table | object | 知识点掌握程度表 |
| data.resource_usage_table | object | 资源使用习惯记录表 |
| data.summary_text | string | 综合文字总结 |

---

## 5. 测验评估

### 接口

`POST /agent/v1/assessment/evaluate`

### 请求示例

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "quiz_id": "quiz_001",
  "questions": [
    {
      "id": "q1",
      "type": "single_choice",
      "content": "栈的出栈顺序属于哪一种？",
      "options": [
        {
          "key": "A",
          "text": "先进先出"
        },
        {
          "key": "B",
          "text": "后进先出"
        },
        {
          "key": "C",
          "text": "随机"
        }
      ],
      "correct_answer": "B",
      "knowledge_point": "栈"
    },
    {
      "id": "q2",
      "type": "multi_choice",
      "content": "下面哪些场景更适合使用队列？",
      "options": [
        {
          "key": "A",
          "text": "打印任务排队"
        },
        {
          "key": "B",
          "text": "函数调用栈"
        },
        {
          "key": "C",
          "text": "消息缓冲"
        }
      ],
      "correct_answer": [
        "A",
        "C"
      ],
      "knowledge_point": "队列"
    }
  ],
  "answers": [
    {
      "question_id": "q1",
      "answer": "B"
    },
    {
      "question_id": "q2",
      "answer": [
        "A"
      ]
    }
  ],
  "user_mastery": {
    "栈": 70,
    "队列": 45
  }
}
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "per_question_results": [
      {
        "question_id": "q1",
        "is_correct": true,
        "explanation": "栈遵循后进先出，因此正确答案是 B。",
        "related_knowledge_points": [
          "栈"
        ]
      },
      {
        "question_id": "q2",
        "is_correct": false,
        "explanation": "打印任务排队和消息缓冲都更符合先进先出的队列特征。",
        "related_knowledge_points": [
          "队列"
        ]
      }
    ],
    "diagnosis": {
      "summary": "用户能识别栈的基本特征，但对队列的典型应用场景掌握不稳定。",
      "weak_points": [
        {
          "name": "队列",
          "error_pattern": "能够记住定义，但在具体场景映射时容易漏选。"
        }
      ],
      "suggestions": [
        "复习队列的先进先出模型",
        "补做 3 道场景判断题强化迁移"
      ]
    }
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| course_id | string | 课程 ID |
| quiz_id | string | 练习 ID |
| questions | array | 题目列表 |
| questions[].id | string | 题目 ID |
| questions[].type | string | 题型 |
| questions[].content | string | 题目内容 |
| questions[].options | array | 选项列表 |
| questions[].correct_answer | string/array | 标准答案，单选为字符串，多选可为数组 |
| questions[].knowledge_point | string | 关联知识点 |
| answers | array | 用户提交答案 |
| answers[].question_id | string | 题目 ID |
| answers[].answer | string/array | 用户答案 |
| user_mastery | object | 用户当前知识点掌握度 |
| data.per_question_results | array | 每题评估结果 |
| data.diagnosis | object | 综合诊断结果 |

---

## 6. 生成题目

### 接口

`POST /agent/v1/assessment/generate-questions`

### 请求示例

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "knowledge_base_id": "kb_ds_c_001",
  "chapter": "栈与队列",
  "knowledge_point": "队列",
  "question_types": [
    "single_choice",
    "multi_choice",
    "short_answer"
  ],
  "count": 3,
  "difficulty": "medium",
  "personalized": true,
  "personalization_context": {
    "evaluation": {
      "summary_text": "用户在队列应用题上容易失分。"
    },
    "profile": {
      "guidance_level_suggestion": {
        "recommended": "L2"
      }
    },
    "wrong_points": [
      {
        "name": "队列",
        "error_count": 3
      }
    ],
    "current_path_node": {
      "id": "node_queue",
      "name": "队列"
    }
  }
}
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "questions": [
      {
        "type": "single_choice",
        "content": "下列哪一种最符合队列的出队规则？",
        "options": [
          {
            "key": "A",
            "text": "后进先出"
          },
          {
            "key": "B",
            "text": "先进先出"
          },
          {
            "key": "C",
            "text": "按优先级弹出"
          }
        ],
        "answer": "B",
        "explanation": "队列的基本规则是先进先出。",
        "chapter": "栈与队列",
        "knowledge_point": "队列",
        "difficulty": "medium"
      },
      {
        "type": "multi_choice",
        "content": "以下哪些应用更适合使用队列？",
        "options": [
          {
            "key": "A",
            "text": "消息缓冲"
          },
          {
            "key": "B",
            "text": "函数调用过程"
          },
          {
            "key": "C",
            "text": "打印任务等待"
          }
        ],
        "answer": [
          "A",
          "C"
        ],
        "explanation": "消息缓冲和打印任务都符合先进先出的调度模式。",
        "chapter": "栈与队列",
        "knowledge_point": "队列",
        "difficulty": "medium"
      }
    ]
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| course_id | string | 课程 ID |
| knowledge_base_id | string | 课程知识库 ID |
| chapter | string | 目标章节 |
| knowledge_point | string | 目标知识点 |
| question_types | array[string] | 题型列表，支持 `single_choice / multi_choice / code / short_answer` |
| count | integer | 生成题数，默认 5 |
| difficulty | string | 难度，`easy / medium / hard` |
| personalized | boolean | 是否生成个性化题 |
| personalization_context | object | 个性化上下文 |
| data.questions | array | 生成题目列表 |
| data.questions[].options | array | 非选择题时可为空数组 |
| data.questions[].answer | string/array | 标准答案 |

---

## 7. 生成学习路径

### 接口

`POST /agent/v1/learning-path/generate`

### 请求示例

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "evaluation": {
    "summary_text": "用户在线性表基础较好，但在栈与队列部分仍需补强。"
  },
  "profile": {
    "knowledge_coordinates": [
      {
        "name": "顺序表",
        "status": "mastered"
      },
      {
        "name": "队列",
        "status": "learning"
      }
    ],
    "guidance_level_suggestion": {
      "recommended": "L2",
      "reason": "建议逐步引导。"
    }
  },
  "knowledge_graph": {
    "nodes": [
      {
        "id": "node_list",
        "name": "线性表",
        "chapter": "线性结构基础"
      },
      {
        "id": "node_stack",
        "name": "栈",
        "chapter": "栈与队列"
      },
      {
        "id": "node_queue",
        "name": "队列",
        "chapter": "栈与队列"
      }
    ],
    "edges": [
      {
        "from": "node_list",
        "to": "node_stack"
      },
      {
        "from": "node_list",
        "to": "node_queue"
      }
    ]
  }
}
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "nodes": [
      {
        "id": "node_list",
        "name": "线性表",
        "status": "completed",
        "mastery": 88,
        "order": 1,
        "reason": "该节点已掌握，可作为后续内容的前置基础。"
      },
      {
        "id": "node_queue",
        "name": "队列",
        "status": "recommended",
        "mastery": 45,
        "order": 2,
        "reason": "当前薄弱点集中在队列应用，需要优先补强。"
      },
      {
        "id": "node_stack",
        "name": "栈",
        "status": "pending",
        "mastery": 60,
        "order": 3,
        "reason": "具备一定基础，可在队列后继续推进。"
      }
    ],
    "edges": [
      {
        "from": "node_list",
        "to": "node_stack"
      },
      {
        "from": "node_list",
        "to": "node_queue"
      }
    ],
    "current_position": {
      "node_id": "node_queue",
      "node_name": "队列"
    }
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| course_id | string | 课程 ID |
| evaluation | object | 学习效果评估数据 |
| profile | object | 用户画像数据 |
| knowledge_graph | object | 静态知识图谱 |
| knowledge_graph.nodes | array | 图谱节点 |
| knowledge_graph.edges | array | 图谱边，表示前置依赖 |
| data.nodes | array | 生成后的学习路径节点 |
| data.nodes[].status | string | `completed / in_progress / pending / recommended` |
| data.nodes[].mastery | number | 掌握度 0-100 |
| data.nodes[].order | integer | 推荐顺序 |
| data.current_position | object | 当前推荐学习位置 |

---

## 8. 生成资源库

### 接口

`POST /agent/v1/resources/generate`

### 请求示例

```json
{
  "task_id": "task_resource_001",
  "user_id": "teacher_001",
  "course_id": "course_ds_c",
  "webhook_url": "http://localhost:8001/api/v1/webhooks/agent",
  "chapter": "栈与队列",
  "knowledge_point": "队列",
  "resource_types": [
    "document",
    "mindmap",
    "reading",
    "code"
  ]
}
```

### 202 响应示例

```json
{
  "code": 202,
  "message": "accepted",
  "data": {
    "task_id": "task_resource_001",
    "estimated_duration": 60
  }
}
```

### Webhook 成功回调示例

```json
{
  "task_id": "task_resource_001",
  "task_type": "resource_generation",
  "status": "completed",
  "result": {
    "resources": [
      {
        "title": "队列核心概念讲义",
        "type": "document",
        "description": "面向课程教学的结构化讲义",
        "content": "# 队列核心概念\n\n队列是一种先进先出的线性结构。",
        "chapter": "栈与队列",
        "knowledge_point": "队列",
        "tags": [
          "队列",
          "FIFO",
          "线性结构"
        ]
      },
      {
        "title": "队列思维导图",
        "type": "mindmap",
        "description": "梳理定义、操作、典型场景",
        "content": "mindmap\n  root((队列))\n    定义\n    基本操作\n    应用场景",
        "chapter": "栈与队列",
        "knowledge_point": "队列",
        "tags": [
          "mindmap",
          "队列"
        ]
      }
    ]
  }
}
```

### Webhook 失败回调示例

```json
{
  "task_id": "task_resource_001",
  "task_type": "resource_generation",
  "status": "failed",
  "error_message": "course_knowledge retrieval failed"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | Backend 预先创建的任务 ID，返回和回调时必须原样带回 |
| user_id | string | 触发教师用户 ID |
| course_id | string | 课程 ID |
| webhook_url | string | Backend 回调地址 |
| chapter | string | 章节 |
| knowledge_point | string | 知识点 |
| resource_types | array[string] | 资源类型列表，支持 `document / mindmap / reading / code` |
| data.task_id | string | 已接受任务的任务 ID |
| data.estimated_duration | integer | 预计完成时间，单位秒 |
| webhook.task_type | string | 固定为 `resource_generation` |
| webhook.status | string | `completed / failed` |
| webhook.result.resources | array | 成功时返回的资源列表 |
| webhook.error_message | string | 失败时错误信息 |

---

## 9. 记忆压缩

### 接口

`POST /agent/v1/memory/compress`

### 请求示例

```json
{
  "user_id": "user_001",
  "conversation_id": "conv_20260527_001",
  "old_summary": "用户已掌握顺序表和链表基础，最近开始学习栈与队列。",
  "messages_to_compress": [
    {
      "role": "user",
      "content": "我总是分不清栈和队列。",
      "timestamp": "2026-05-27T09:00:00Z"
    },
    {
      "role": "assistant",
      "content": "你可以先记住栈是后进先出，队列是先进先出。",
      "timestamp": "2026-05-27T09:00:20Z"
    },
    {
      "role": "user",
      "content": "那打印任务排队更像队列。",
      "timestamp": "2026-05-27T09:01:00Z"
    }
  ],
  "existing_facts": [
    "fact_001",
    "fact_002"
  ]
}
```

### 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "new_summary": "用户已理解线性表基础，正在学习栈与队列，能够初步判断队列在排队类场景中的应用，但两者的抽象区别仍需强化。",
    "extracted_facts": [
      {
        "content": "用户在栈和队列概念区分上存在持续困惑。",
        "fact_type": "blind_spot",
        "knowledge_point": "栈与队列",
        "confidence": 0.92
      },
      {
        "content": "用户能够将打印任务排队识别为队列场景。",
        "fact_type": "mastered_point",
        "knowledge_point": "队列应用",
        "confidence": 0.81
      }
    ]
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| conversation_id | string | 对话 ID |
| old_summary | string | 旧的全局摘要，首次压缩可为空 |
| messages_to_compress | array | 本轮待压缩消息 |
| messages_to_compress[].role | string | `user / assistant` |
| messages_to_compress[].content | string | 消息内容 |
| messages_to_compress[].timestamp | string | 消息时间，建议 ISO 8601 |
| existing_facts | array[string] | 已存储事实 ID，用于去重 |
| data.new_summary | string | 融合后的新摘要 |
| data.extracted_facts | array | 提取出的长期记忆事实 |
| data.extracted_facts[].fact_type | string | `blind_spot / mastered_point / cognitive_preference` |
| data.extracted_facts[].knowledge_point | string | 关联知识点 |
| data.extracted_facts[].confidence | number | 置信度 0-1 |

---

## 10. Apifox 使用建议

### 同步 JSON 接口

可直接把“请求示例”和“响应示例”复制到 Apifox 的 Body 示例中使用。

### SSE 接口

Apifox 如果不方便完整模拟 `text/event-stream`，建议按单条 JSON 事件做多个 Mock 示例：

- `chunk`
- `diagram`
- `knowledge_points`
- `suggestion`
- `done`

实际 SSE 线上格式为：

```text
data: {"type":"chunk","content":"..."}
```

### 异步资源接口

建议在 Apifox 中拆成 3 份示例：

- `POST /agent/v1/resources/generate` 的 `202` 响应
- webhook 成功回调 payload
- webhook 失败回调 payload
