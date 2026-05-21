# EduAgent 系统 API 交互规范说明 (v3.0 最终版)

基于《需求规格说明书1.1.docx》的最新需求，本规范明确了“关系型数据库（后端）与向量库（Agent）分离”、“事件驱动更新画像”、“异步生成资源”、“Chat+Tool”以及“6维度动态画像”的架构设计。

本文档可直接作为 Apifox 接口录入的标准参考。

---

## 一、 全局规范 (Global Standards)

*   **前端 -> 后端 (Frontend to Backend)**：基础 URL 假设为 `https://api.eduagent.com/v1`，需要在 Header 携带 `Authorization: Bearer <token>`（除注册登录外）。
*   **后端 -> Agent (Backend to Agent)**：基础 URL 假设为 `http://agent-service:8002/v1`，走内网 RPC 调用，无需鉴权。
*   **标准返回结构 (JSON)**：
    ```json
    {
      "code": 200,          // 200:成功, 400:参数错误, 401:未授权, 500:服务器内部错误
      "message": "success", // 错误时的具体提示信息
      "data": { ... }       // 实际业务数据对象或数组，失败时为 null
    }
    ```

---

## 二、 前端 ↔ 后端接口 (Frontend to Backend)
*该部分接口由前端调用，后端（如 Java/Go/Python Web）提供服务，直接操作 SQLite/MySQL 关系型数据库。*

### 1. 基础业务 (Auth & User)

#### 1.1 获取图形验证码
*   **GET** `/api/v1/auth/captcha`
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": {
        "captcha_token": "token_abc123",
        "captcha_image": "data:image/png;base64,iVBORw0KGgo..."
      }
    }
    ```

#### 1.2 用户注册
*   **POST** `/api/v1/auth/register`
*   **功能描述**: 用户需要经过系统管理层管理员分发账户注册码，通过邮箱进行注册。
*   **Request**:
    ```json
    {
      "email": "student@example.com",
      "username": "student_01",
      "password": "password123",
      "registration_code": "STU_2026_ABC"
    }
    ```
*   **Response**: `{"code": 200, "message": "注册成功", "data": null}`

#### 1.3 用户登录
*   **POST** `/api/v1/auth/login`
*   **功能描述**: 邮箱+密码+图形验证码登录。
*   **Request**:
    ```json
    {
      "email": "student@example.com",
      "password": "password123",
      "captcha_code": "abcd",
      "captcha_token": "token_abc123"
    }
    ```
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "登录成功",
      "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "expires_in": 3600
      }
    }
    ```

#### 1.4 发送邮箱验证码 (找回密码用)
*   **POST** `/api/v1/auth/send-code`
*   **Request**:
    ```json
    {
      "email": "student@example.com"
    }
    ```
*   **Response**: `{"code": 200, "message": "验证码发送成功", "data": null}`

#### 1.5 找回密码
*   **POST** `/api/v1/auth/reset-password`
*   **Request**:
    ```json
    {
      "email": "student@example.com",
      "verification_code": "123456",
      "new_password": "newpassword123"
    }
    ```
*   **Response**: `{"code": 200, "message": "密码重置成功", "data": null}`

#### 1.6 获取用户信息与当前画像 (6维度画像)
*   **GET** `/api/v1/user/info`
*   **功能描述**: 获取用户基础信息及 6 维度动态画像数据，用于前端渲染雷达图、滑块、标签云等。
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": {
        "user_id": "u_123",
        "username": "student_01",
        "role": "student",
        "profile": {
          "modality_preference": { "video": 30, "chart": 25, "text": 15, "code": 20, "formula": 10 },
          "guidance_level": "L2",
          "knowledge_coordinates": { "mastered": ["顺序表", "链表"], "learning": ["二叉树遍历"] },
          "cognitive_blind_spots": ["递归边界条件", "指针越界"],
          "drive_intent": "daily",
          "discipline_base": "bronze"
        },
        "current_path_node": "二叉树遍历"
      }
    }
    ```

---

### 2. 核心 AI 业务 (AI Features)

#### 2.1 智能对话 (Chatbot + Tool) - [SSE 流式接口]
*   **POST** `/api/v1/chat/completions`
*   **功能描述**: 前端发送聊天消息，后端接收后去数据库查出最近 N 轮历史和用户画像，调用 Agent 接口，并将 Agent 返回的流透传给前端。
*   **Request**:
    ```json
    {
      "session_id": "sess_9527",
      "message": "能给我画个二叉树遍历的图吗？"
    }
    ```
*   **Response (SSE Stream)**:
    前端需要根据 `event` 类型分别处理：普通文本直接打字机输出；`tool_call` 则拦截下来渲染图表。
    ```text
    event: text
    data: {"content": "好的，二叉树的遍历通常分为前序、中序和后序。"}

    event: tool_call
    data: {"tool_name": "draw_diagram", "tool_args": {"type": "mermaid", "code": "graph TD;\n A-->B;\n A-->C;"}}

    event: done
    data: {"status": "finished"}
    ```

#### 2.2 提交测验 (触发画像与路径更新) - [同步接口]
*   **POST** `/api/v1/assessment/submit`
*   **功能描述**: 学生做完题提交，后端将答题数据发给 Agent 评估，Agent 返回结构化结果后，后端更新 SQL 中的画像和路径表。
*   **Request**:
    ```json
    {
      "knowledge_point_id": "kp_tree_01",
      "answers": {
        "q1": "A",
        "q2": "C",
        "q3": "B"
      }
    }
    ```
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": {
        "score": 85,
        "evaluation": "你对前序遍历掌握得很好，但在递归边界条件上还有欠缺。",
        "mastery_level_changed": true // 提示前端可以去拉取新的画像和路径了
      }
    }
    ```

#### 2.3 获取学习效果评估图表数据
*   **GET** `/api/v1/assessment/evaluation-charts`
*   **功能描述**: 获取用户的学习进度表、测试掌握程度表、资源使用习惯表，以及大模型的文字总结。
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": {
        "progress_data": [{"module": "线性表", "progress": 100}, {"module": "树", "progress": 40}],
        "mastery_data": [{"knowledge_point": "前序遍历", "score": 90}, {"knowledge_point": "递归", "score": 45}],
        "resource_usage_data": [{"type": "video", "ratio": 0.6}, {"type": "text", "ratio": 0.4}],
        "ai_summary": "该生近期在二叉树章节学习积极，但测试中反映出对递归的掌握仍有欠缺，偏好视频类资源..."
      }
    }
    ```

#### 2.4 获取主页推荐资源 (路径资源推送) - [同步接口]
*   **GET** `/api/v1/recommendations/daily`
*   **功能描述**: 前端一登录/进主页就调用。后端直接从 SQL 数据库中查出与该用户当前“学习路径”匹配的、已经生成好的静态资源列表。
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": [
        {
          "resource_id": "res_001",
          "type": "mindmap",
          "title": "二叉树核心知识点导图",
          "content_url": "https://static.eduagent.com/res/001.json"
        },
        {
          "resource_id": "res_002",
          "type": "quiz",
          "title": "递归算法专项练习5题",
          "content_url": null
        }
      ]
    }
    ```

#### 2.5 触发多类型资源生成 - [异步接口]
*   **POST** `/api/v1/resource/generate`
*   **功能描述**: 用户主动要求生成某知识点的资料。后端在 SQL 创建一条 `pending` 记录，然后异步调 Agent。
*   **Request**:
    ```json
    {
      "knowledge_point": "红黑树",
      "resource_types": ["explanation_doc", "quiz"]
    }
    ```
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "任务已提交，后台生成中",
      "data": {
        "task_id": "task_8848",
        "status": "pending"
      }
    }
    ```

---

### 3. 课程与班级管理 (Course & Class Management)

#### 3.1 教师生成课程码
*   **POST** `/api/v1/course/generate-code`
*   **功能描述**: 教师端调用，生成一个唯一的课程邀请码，用于分发给学生。
*   **Request**:
    ```json
    {
      "course_name": "数据结构与算法(2026春)"
    }
    ```
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "课程创建成功",
      "data": {
        "course_id": "c_1001",
        "course_code": "DS2026",
        "course_name": "数据结构与算法(2026春)"
      }
    }
    ```

#### 3.2 学生加入课程
*   **POST** `/api/v1/course/join`
*   **功能描述**: 学生端调用，输入教师提供的课程码，绑定师生关系。
*   **Request**:
    ```json
    {
      "course_code": "DS2026"
    }
    ```
*   **Response**: `{"code": 200, "message": "成功加入课程", "data": null}`

#### 3.3 教师获取班级学生列表及数据
*   **GET** `/api/v1/course/{course_id}/students`
*   **功能描述**: 教师端调用，查看该课程下所有学生的学习进度、画像等数据（复用学生个人数据组件）。
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": [
        {
          "user_id": "u_123",
          "username": "student_01",
          "profile": {
            "modality_preference": { "video": 30, "chart": 25, "text": 15, "code": 20, "formula": 10 },
            "guidance_level": "L2",
            "knowledge_coordinates": { "mastered": ["顺序表", "链表"], "learning": ["二叉树遍历"] },
            "cognitive_blind_spots": ["递归边界条件", "指针越界"],
            "drive_intent": "daily",
            "discipline_base": "bronze"
          },
          "current_path_node": "二叉树遍历",
          "overall_score": 85
        }
      ]
    }
    ```

---

### 4. 系统管理 (System Admin)

#### 4.1 管理员分发注册码
*   **POST** `/api/v1/admin/registration-codes`
*   **功能描述**: 管理员生成注册码，编码中包含角色信息（如 `STU_` 开头代表学生，`TEA_` 开头代表教师）。
*   **Request**:
    ```json
    {
      "role": "student",
      "count": 50
    }
    ```
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": ["STU_A1B2", "STU_C3D4", "..."]
    }
    ```

#### 4.2 获取系统运行日志
*   **GET** `/api/v1/admin/logs`
*   **功能描述**: 管理员查看智能体运行情况（延迟、Token消耗）、安全拦截记录等。
*   **Response**:
    ```json
    {
      "code": 200,
      "message": "success",
      "data": [
        {"time": "2026-04-28 10:00:00", "type": "agent_latency", "value": "1.2s", "details": "Chatbot response"},
        {"time": "2026-04-28 10:05:00", "type": "security_block", "value": "幻觉拦截", "details": "Blocked invalid API generation"}
      ]
    }
    ```

---

## 三、 后端 ↔ Agent 内部接口 (Backend to Agent)
*该部分接口由后端发起调用，Agent 提供服务。Agent 必须强制使用 Structured Outputs (如 Pydantic) 保证返回严格的 JSON 结构，防止后端解析崩溃。*

### 1. 记忆压缩与反馈总结 (小模型处理)
*   **POST** `/agent/v1/memory/compress`
*   **功能描述**: 聊天满 10 轮后，后端把这 10 轮原始记录发给 Agent，Agent 提取事实存入向量库，并返回一段新的 Summary 给后端存 SQL。
*   **Request**:
    ```json
    {
      "user_id": "u_123",
      "old_summary": "用户是个初学者，正在学C语言。",
      "recent_dialogues": [
        {"role": "user", "content": "指针太难了，总是段错误"},
        {"role": "assistant", "content": "..."}
      ]
    }
    ```
*   **Response (强制 JSON 结构)**:
    ```json
    {
      "new_summary": "用户是个初学者，正在学C语言。目前在学习指针，经常遇到段错误，对内存地址概念模糊。",
      "extracted_facts": ["卡点：指针段错误", "偏好：需要图解内存"]
    }
    ```

### 2. 测验评估与画像/路径更新 (大模型处理)
*   **POST** `/agent/v1/assessment/evaluate`
*   **功能描述**: 后端将学生的答题情况发给 Agent，Agent 结合底层图谱计算出新的掌握度，并推荐下一步学什么。
*   **Request**:
    ```json
    {
      "user_id": "u_123",
      "current_profile": {"guidance_level": "L2"},
      "current_mastery": {"二叉树": 0.5},
      "quiz_data": { "questions": [...], "user_answers": [...] }
    }
    ```
*   **Response (强制 JSON 结构)**:
    ```json
    {
      "evaluation_text": "递归边界条件掌握不佳...",
      "score": 85,
      "updated_profile": {
        "guidance_level": "L3",
        "cognitive_blind_spots": ["递归边界条件"]
      },
      "updated_mastery": {
        "二叉树": 0.6,
        "递归": 0.3
      },
      "recommended_next_nodes": ["递归基线条件", "调用栈原理"]
    }
    ```

### 3. 异步资源生成 (Manager-Worker)
*   **POST** `/agent/v1/resource/generate`
*   **功能描述**: 后端通知 Agent 开始后台生成资源。
*   **Request**:
    ```json
    {
      "task_id": "task_8848",
      "knowledge_point": "红黑树",
      "user_profile": {"modality_preference": {"video": 80}},
      "types": ["quiz"]
    }
    ```
*   **Response**: 
    ```json
    {
      "status": "accepted"
    }
    ```

### 4. 资源生成完成回调 (Agent -> Backend Webhook)
*   **POST** `http://backend-api/internal/webhook/resource_completed`
*   **功能描述**: Agent 跑完后，把结构化的数据推回给后端，后端存入 SQL。
*   **Request (Agent 发送给后端)**:
    ```json
    {
      "task_id": "task_8848",
      "status": "success",
      "generated_resources": {
        "quiz": [
          {
            "question": "红黑树的根节点是什么颜色？",
            "options": {"A": "红色", "B": "黑色"},
            "answer": "B",
            "explanation": "根据红黑树性质1..."
          }
        ]
      }
    }
    ```
*   **Response**: `{"code": 200, "message": "Webhook received", "data": null}`