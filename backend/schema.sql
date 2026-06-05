-- ============================================================
-- DUagent Database Schema (MySQL 8.0+)
-- Host: localhost:3306, User: root, Password: 123456
-- Database: duagent
-- ============================================================

CREATE DATABASE IF NOT EXISTS duagent
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE duagent;

-- ============================================================
-- 1. users — 用户表
-- ============================================================
CREATE TABLE users (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '用户ID',
    username        VARCHAR(50)   NOT NULL COMMENT '用户名，3-20位',
    email           VARCHAR(120)  NOT NULL COMMENT '邮箱地址',
    password_hash   VARCHAR(255)  NOT NULL COMMENT '密码哈希',
    real_name       VARCHAR(50)   NOT NULL DEFAULT '' COMMENT '真实姓名',
    student_id      VARCHAR(30)   NOT NULL DEFAULT '' COMMENT '学号或工号',
    role            VARCHAR(20)   NOT NULL DEFAULT 'student' COMMENT '角色：student/teacher/admin',
    major           VARCHAR(100)  NOT NULL DEFAULT '' COMMENT '专业',
    grade           VARCHAR(20)   NOT NULL DEFAULT '' COMMENT '年级',
    guidance_level  VARCHAR(5)    NOT NULL DEFAULT 'L2' COMMENT '引导粒度：L1/L2/L3',
    is_active       TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否启用：1启用 0禁用',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志：0正常 1已删除',
    UNIQUE INDEX uk_username (username),
    UNIQUE INDEX uk_email (email),
    INDEX idx_role (role),
    INDEX idx_is_active (is_active),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';


-- ============================================================
-- 2. registration_codes — 注册码表
-- ============================================================
CREATE TABLE registration_codes (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '主键ID',
    code            VARCHAR(50)   NOT NULL COMMENT '注册码，v1硬编码为student/teacher',
    role            VARCHAR(20)   NOT NULL COMMENT '对应角色',
    is_used         TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否已使用',
    used_by         VARCHAR(32)   DEFAULT NULL COMMENT '使用者用户ID',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    UNIQUE INDEX uk_code (code),
    INDEX idx_is_used (is_used),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='注册码表';


-- ============================================================
-- 3. courses — 课程/班级表
-- ============================================================
CREATE TABLE courses (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '课程ID',
    name            VARCHAR(100)  NOT NULL COMMENT '课程名称',
    description     TEXT          DEFAULT NULL COMMENT '课程描述',
    course_code     VARCHAR(20)   NOT NULL COMMENT '唯一课程码',
    teacher_id      VARCHAR(32)   NOT NULL COMMENT '授课教师用户ID',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    UNIQUE INDEX uk_course_code (course_code),
    INDEX idx_teacher (teacher_id),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_courses_teacher FOREIGN KEY (teacher_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='课程/班级表';


-- ============================================================
-- 4. course_enrollments — 选课/加入记录表
-- ============================================================
CREATE TABLE course_enrollments (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '主键ID',
    student_id      VARCHAR(32)   NOT NULL COMMENT '学生用户ID',
    course_id       VARCHAR(32)   NOT NULL COMMENT '课程ID',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志（退出课程）',
    UNIQUE INDEX uk_student_course (student_id, course_id),
    INDEX idx_course (course_id),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_enroll_student FOREIGN KEY (student_id) REFERENCES users(id),
    CONSTRAINT fk_enroll_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='选课/加入记录表';


-- ============================================================
-- 5. quiz_questions — 题库表（通用题+个性化题）
-- ============================================================
CREATE TABLE quiz_questions (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '题目ID',
    course_id       VARCHAR(32)   NOT NULL COMMENT '所属课程ID',
    chapter         VARCHAR(100)  NOT NULL DEFAULT '' COMMENT '所属章节',
    knowledge_point VARCHAR(100)  NOT NULL DEFAULT '' COMMENT '关联知识点',
    type            VARCHAR(20)   NOT NULL COMMENT '题型：single_choice/multi_choice/code/short_answer',
    source          VARCHAR(20)   NOT NULL DEFAULT 'common' COMMENT '来源：common/personalized',
    personalized    TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否个性化题',
    owner_user_id   VARCHAR(32)   DEFAULT NULL COMMENT '个性化题归属用户ID，通用题为NULL',
    difficulty      VARCHAR(10)   NOT NULL DEFAULT 'medium' COMMENT '难度：easy/medium/hard',
    content         TEXT          NOT NULL COMMENT '题目内容',
    options         JSON          DEFAULT NULL COMMENT '选项列表：[{key,text}]，非选择题为[]',
    correct_answer  VARCHAR(500)  NOT NULL COMMENT '正确答案',
    explanation     TEXT          DEFAULT NULL COMMENT '题目解析',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_course (course_id),
    INDEX idx_chapter (chapter),
    INDEX idx_knowledge_point (knowledge_point),
    INDEX idx_type (type),
    INDEX idx_source (source),
    INDEX idx_owner (owner_user_id),
    INDEX idx_difficulty (difficulty),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_qq_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='题库表';


-- ============================================================
-- 6. quiz_sessions — 练习会话表
-- ============================================================
CREATE TABLE quiz_sessions (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '练习会话ID',
    user_id         VARCHAR(32)   NOT NULL COMMENT '答题用户ID',
    course_id       VARCHAR(32)   NOT NULL COMMENT '课程ID',
    chapter         VARCHAR(100)  NOT NULL DEFAULT '' COMMENT '章节',
    score           DECIMAL(5,1)  NOT NULL DEFAULT 0.0 COMMENT '正确率 0-100',
    correct_count   INT           NOT NULL DEFAULT 0 COMMENT '正确题数',
    total_count     INT           NOT NULL DEFAULT 0 COMMENT '总题数',
    time_spent      INT           NOT NULL DEFAULT 0 COMMENT '答题总耗时（秒）',
    diagnosis_json  JSON          DEFAULT NULL COMMENT 'LLM诊断结果JSON',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '完成时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_user (user_id),
    INDEX idx_course (course_id),
    INDEX idx_user_course (user_id, course_id),
    INDEX idx_create_time (create_time),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_qs_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_qs_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='练习会话表';


-- ============================================================
-- 7. quiz_answers — 答题明细表
-- ============================================================
CREATE TABLE quiz_answers (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '主键ID',
    quiz_id         VARCHAR(32)   NOT NULL COMMENT '练习会话ID',
    question_id     VARCHAR(32)   NOT NULL COMMENT '题目ID',
    user_answer     VARCHAR(500)  NOT NULL DEFAULT '' COMMENT '用户答案',
    is_correct      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否正确',
    correct_answer  VARCHAR(500)  NOT NULL DEFAULT '' COMMENT '正确答案',
    explanation     TEXT          DEFAULT NULL COMMENT '解析（LLM异步生成）',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_quiz (quiz_id),
    INDEX idx_question (question_id),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_qa_quiz FOREIGN KEY (quiz_id) REFERENCES quiz_sessions(id),
    CONSTRAINT fk_qa_question FOREIGN KEY (question_id) REFERENCES quiz_questions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='答题明细表';


-- ============================================================
-- 8. conversations — 智能辅导对话表
-- ============================================================
CREATE TABLE conversations (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '对话ID',
    user_id         VARCHAR(32)   NOT NULL COMMENT '所属用户ID',
    scope           VARCHAR(20)   NOT NULL DEFAULT 'course' COMMENT '对话范围：course/global',
    course_id       VARCHAR(32)   DEFAULT NULL COMMENT '关联课程ID，全局对话为NULL',
    title           VARCHAR(200)  NOT NULL COMMENT '对话标题',
    summary         TEXT          DEFAULT NULL COMMENT '记忆压缩后的全局对话摘要，供 Agent /tutoring/chat 的 conversation_summary 使用',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_user (user_id),
    INDEX idx_course (course_id),
    INDEX idx_scope (scope),
    INDEX idx_user_scope (user_id, scope),
    INDEX idx_update_time (update_time),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_conv_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_conv_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='智能辅导对话表';


-- ============================================================
-- 9. messages — 对话消息表
-- ============================================================
CREATE TABLE messages (
    id                VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '消息ID',
    conversation_id   VARCHAR(32)   NOT NULL COMMENT '所属对话ID',
    role              VARCHAR(10)   NOT NULL COMMENT '角色：user/assistant',
    content           TEXT          DEFAULT NULL COMMENT '消息内容',
    diagrams          JSON          DEFAULT NULL COMMENT '内嵌图解',
    knowledge_points  JSON          DEFAULT NULL COMMENT '引用的知识点',
    meta_json         JSON          DEFAULT NULL COMMENT '消息元信息：scope/course_id/model_name/token_count/safety_flags等',
    create_time       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '消息时间',
    create_by         VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by         VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted        TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_conversation (conversation_id),
    INDEX idx_role (role),
    INDEX idx_create_time (create_time),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_msg_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话消息表';


-- ============================================================
-- 10. resources — 学习资源表
-- ============================================================
CREATE TABLE resources (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '资源ID',
    course_id       VARCHAR(32)   NOT NULL COMMENT '所属课程ID',
    title           VARCHAR(200)  NOT NULL COMMENT '资源标题',
    type            VARCHAR(30)   NOT NULL COMMENT '类型：document/mindmap/reading/code/video',
    description     TEXT          DEFAULT NULL COMMENT '资源描述',
    tags            JSON          DEFAULT NULL COMMENT '标签列表',
    chapter         VARCHAR(100)  NOT NULL DEFAULT '' COMMENT '所属章节',
    knowledge_point VARCHAR(100)  NOT NULL DEFAULT '' COMMENT '关联知识点',
    content         MEDIUMTEXT    DEFAULT NULL COMMENT '资源正文内容（Markdown/JSON/Mermaid等）',
    url             VARCHAR(500)  NOT NULL DEFAULT '' COMMENT '资源链接',
    view_count      INT           NOT NULL DEFAULT 0 COMMENT '浏览次数',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_course (course_id),
    INDEX idx_type (type),
    INDEX idx_chapter (chapter),
    INDEX idx_knowledge_point (knowledge_point),
    INDEX idx_view_count (view_count),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_res_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学习资源表';


-- ============================================================
-- 11. async_tasks — 异步任务表
-- ============================================================
CREATE TABLE async_tasks (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '任务ID',
    task_type       VARCHAR(30)   NOT NULL COMMENT '任务类型：evaluation_refresh/profile_refresh/learning_path_refresh/quiz_generation/resource_generation',
    status          VARCHAR(20)   NOT NULL DEFAULT 'processing' COMMENT '状态：processing/completed/failed',
    progress        INT           NOT NULL DEFAULT 0 COMMENT '进度百分比 0-100',
    user_id         VARCHAR(32)   DEFAULT NULL COMMENT '发起用户ID',
    course_id       VARCHAR(32)   DEFAULT NULL COMMENT '关联课程ID',
    result          JSON          DEFAULT NULL COMMENT '任务结果摘要',
    error_code      VARCHAR(20)   DEFAULT NULL COMMENT '错误码',
    error_message   VARCHAR(500)  DEFAULT ''   COMMENT '错误信息',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    completed_at    DATETIME      DEFAULT NULL COMMENT '完成时间',
    INDEX idx_task_type (task_type),
    INDEX idx_status (status),
    INDEX idx_user (user_id),
    INDEX idx_course (course_id),
    INDEX idx_create_time (create_time),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_task_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_task_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异步任务表。资源生成链路：Backend创建task后调用Agent /resources/generate，传入task_id/user_id/course_id/webhook_url；Agent回调webhook时携带task_id和result.resources，Backend校验task_type后幂等写入resources表';


-- ============================================================
-- 12. evaluations — 学习效果评估表
-- ============================================================
CREATE TABLE evaluations (
    id                  VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '评估记录ID',
    user_id             VARCHAR(32)   NOT NULL COMMENT '用户ID',
    course_id           VARCHAR(32)   NOT NULL COMMENT '课程ID',
    progress_table      JSON          DEFAULT NULL COMMENT '学习进度表 {columns:[{key,title}],rows:[{}]}',
    mastery_table       JSON          DEFAULT NULL COMMENT '知识点掌握程度表',
    resource_usage_table JSON         DEFAULT NULL COMMENT '资源使用习惯记录表',
    summary_text        TEXT          DEFAULT NULL COMMENT 'LLM文字总结',
    create_time         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by           VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by           VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted          TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    generated_at        DATETIME      DEFAULT NULL COMMENT '评估生成时间',
    INDEX idx_user_course (user_id, course_id),
    INDEX idx_generated_at (generated_at),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_eval_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_eval_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学习效果评估表';


-- ============================================================
-- 13. user_profiles — 用户画像表
-- ============================================================
CREATE TABLE user_profiles (
    id                      VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '画像记录ID',
    user_id                 VARCHAR(32)   NOT NULL COMMENT '用户ID',
    course_id               VARCHAR(32)   NOT NULL COMMENT '课程ID',
    modal_preference        JSON          DEFAULT NULL COMMENT '模态偏好五维数据',
    guidance_level_current  VARCHAR(5)    NOT NULL DEFAULT 'L2' COMMENT '当前引导粒度',
    guidance_level_updated_at DATETIME    DEFAULT NULL   COMMENT '引导粒度更新时间',
    knowledge_mastered      INT           NOT NULL DEFAULT 0 COMMENT '已掌握知识点数量',
    knowledge_weak          INT           NOT NULL DEFAULT 0 COMMENT '薄弱知识点数量',
    knowledge_coordinates   JSON          DEFAULT NULL COMMENT '知识坐标',
    cognitive_blindspots    JSON          DEFAULT NULL COMMENT '认知盲区',
    drive_intent            JSON          DEFAULT NULL COMMENT '驱动意图',
    discipline_badge        JSON          DEFAULT NULL COMMENT '学科徽章',
    create_time             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by               VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by               VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted              TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    generated_at            DATETIME      DEFAULT NULL COMMENT '画像生成时间',
    UNIQUE INDEX uk_user_course (user_id, course_id),
    INDEX idx_generated_at (generated_at),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_up_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_up_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户画像表';


-- ============================================================
-- 14. learning_paths — 学习路径表
-- ============================================================
CREATE TABLE learning_paths (
    id                VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '路径记录ID',
    user_id           VARCHAR(32)   NOT NULL COMMENT '用户ID',
    course_id         VARCHAR(32)   NOT NULL COMMENT '课程ID',
    nodes             JSON          DEFAULT NULL COMMENT '路径节点列表',
    edges             JSON          DEFAULT NULL COMMENT '节点依赖边',
    current_node_id   VARCHAR(32)   NOT NULL DEFAULT '' COMMENT '当前节点ID',
    current_node_name VARCHAR(100)  NOT NULL DEFAULT '' COMMENT '当前节点名称',
    create_time       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by         VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by         VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted        TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    generated_at      DATETIME      DEFAULT NULL COMMENT '路径生成时间',
    INDEX idx_user_course (user_id, course_id),
    INDEX idx_generated_at (generated_at),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_lp_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_lp_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学习路径表';


-- ============================================================
-- 15. course_knowledge_graphs — 课程静态知识图谱表
-- ============================================================
-- Backend 调用 Agent /learning-path/generate 时传入 knowledge_graph.nodes/edges。
-- 来源：开发者预置 JSON 或从课程资源/向量库导出，每门课一条记录。
CREATE TABLE course_knowledge_graphs (
    id              VARCHAR(32)   NOT NULL PRIMARY KEY COMMENT '图谱记录ID',
    course_id       VARCHAR(32)   NOT NULL COMMENT '课程ID',
    nodes           JSON          NOT NULL COMMENT '知识图谱节点 [{id, name, chapter}]',
    edges           JSON          NOT NULL COMMENT '前置依赖边 [{from, to}]',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    UNIQUE INDEX uk_course (course_id),
    INDEX idx_is_deleted (is_deleted),
    CONSTRAINT fk_ckg_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='课程静态知识图谱表';


-- ============================================================
-- 16. agent_logs — Agent运行日志表
-- ============================================================
CREATE TABLE agent_logs (
    id              BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    timestamp       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '时间戳',
    agent_type      VARCHAR(20)   NOT NULL COMMENT 'Agent类型：tutoring/evaluation/profile/assessment/learning_path/resource/memory/health',
    endpoint        VARCHAR(200)  NOT NULL DEFAULT '' COMMENT '调用的Agent接口路径',
    latency_ms      INT           NOT NULL DEFAULT 0 COMMENT '响应延迟（毫秒）',
    tokens_used     INT           NOT NULL DEFAULT 0 COMMENT 'Token消耗',
    status          VARCHAR(10)   NOT NULL DEFAULT 'success' COMMENT '状态：success/error',
    error_message   VARCHAR(500)  DEFAULT NULL COMMENT '错误信息',
    security_blocked TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否触发安全拦截',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_timestamp (timestamp),
    INDEX idx_agent_type (agent_type),
    INDEX idx_status (status),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent运行日志表';


-- ============================================================
-- 17. operation_logs — 系统运行日志表
-- ============================================================
CREATE TABLE operation_logs (
    id              BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    timestamp       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '时间戳',
    event_type      VARCHAR(30)   NOT NULL COMMENT '事件类型：login/logout/operation/system_error/security',
    user_id         VARCHAR(32)   DEFAULT NULL COMMENT '关联用户ID',
    description     VARCHAR(300)  NOT NULL DEFAULT '' COMMENT '事件描述',
    ip_address      VARCHAR(45)   NOT NULL DEFAULT '' COMMENT 'IP地址',
    detail          JSON          DEFAULT NULL COMMENT '事件详细数据',
    create_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    create_by       VARCHAR(32)   DEFAULT NULL COMMENT '创建人ID',
    update_time     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
    update_by       VARCHAR(32)   DEFAULT NULL COMMENT '修改人ID',
    is_deleted      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '假删标志',
    INDEX idx_timestamp (timestamp),
    INDEX idx_event_type (event_type),
    INDEX idx_user_id (user_id),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统运行日志表';


-- ============================================================
-- 预置管理员账号 (admin@admin.com / Admin123456)
-- ============================================================
INSERT INTO users (id, username, email, password_hash, real_name, role, create_by)
VALUES ('admin000000000000000000000001', 'admin', 'admin@admin.com',
        '$2b$12$LJ3m4ys3GZfnYMz8kVsKaOTSxGHLfEhCgJwW3MlFJrpPqk0mPQYSu',
        '系统管理员', 'admin', 'system');
-- Password: Admin123456 (bcrypt hash — replace with actual hash after first run)


-- ============================================================
-- 预置注册码
-- ============================================================
INSERT INTO registration_codes (id, code, role, create_by)
VALUES ('rc00000000000000000000000001', 'student', 'student', 'system'),
       ('rc00000000000000000000000002', 'teacher', 'teacher', 'system');
