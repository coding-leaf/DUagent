-- ============================================================
-- EduAgent 数据库结构定义
-- 基于当前 MySQL 22 表实际结构自动生成 (2026-06-16)
-- 使用前请先执行 schema.sql，再依次执行 migrations/ 下的迁移
-- ============================================================

CREATE TABLE IF NOT EXISTS `users` (
  `id` VARCHAR(32) NOT NULL,
  `username` VARCHAR(50) NOT NULL,
  `email` VARCHAR(120) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `real_name` VARCHAR(50) NOT NULL,
  `student_id` VARCHAR(30) NOT NULL,
  `role` VARCHAR(20) NOT NULL COMMENT '角色：student/teacher/admin',
  `major` VARCHAR(100) NOT NULL DEFAULT '',
  `grade` VARCHAR(20) NOT NULL DEFAULT '',
  `guidance_level` VARCHAR(5) NOT NULL DEFAULT 'L2' COMMENT '引导粒度：L1/L2/L3',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 预置管理员账号 (admin@admin.com / Admin123456)
INSERT INTO users (id, username, email, password_hash, real_name, student_id, role, major, grade, guidance_level, is_active, is_deleted, create_by)
VALUES ('admin000000000000000000000001', 'admin', 'admin@admin.com',
        '$2b$12$k4zj0wRQqBBbfYHl3YGhJOjYhdXZijOubyMDT1Lk2OmuDP1D5kOcm',
        '系统管理员', 'ADMIN001', 'admin', '', '', 'L2', 1, 0, 'system');

-- ============================================================
-- 注册码
-- ============================================================
CREATE TABLE IF NOT EXISTS `registration_codes` (
  `id` VARCHAR(32) NOT NULL,
  `code` VARCHAR(50) NOT NULL,
  `role` VARCHAR(20) NOT NULL,
  `is_used` TINYINT(1) NOT NULL DEFAULT 0,
  `used_by` VARCHAR(32) DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 课程
-- ============================================================
CREATE TABLE IF NOT EXISTS `courses` (
  `id` VARCHAR(32) NOT NULL,
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `course_code` VARCHAR(20) NOT NULL,
  `teacher_id` VARCHAR(32) NOT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `course_code` (`course_code`),
  KEY `teacher_id` (`teacher_id`),
  CONSTRAINT `courses_ibfk_1` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 课程选课
-- ============================================================
CREATE TABLE IF NOT EXISTS `course_enrollments` (
  `id` VARCHAR(32) NOT NULL,
  `student_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `student_id` (`student_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `course_enrollments_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`),
  CONSTRAINT `course_enrollments_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 课程目录（课程素材管理）
-- ============================================================
CREATE TABLE IF NOT EXISTS `course_catalogs` (
  `id` VARCHAR(32) NOT NULL,
  `title` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `status` VARCHAR(20) NOT NULL,
  `knowledge_status` VARCHAR(20) NOT NULL,
  `material_count` INT NOT NULL DEFAULT 0,
  `last_ingestion_task_id` VARCHAR(32) DEFAULT NULL,
  `last_ingestion_status` VARCHAR(20) DEFAULT NULL,
  `chunk_count` INT NOT NULL DEFAULT 0,
  `last_error` VARCHAR(500) DEFAULT NULL,
  `kg_host_course_id` VARCHAR(32) DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `kg_host_course_id` (`kg_host_course_id`),
  CONSTRAINT `course_catalogs_ibfk_1` FOREIGN KEY (`kg_host_course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 课程目录素材文件
-- ============================================================
CREATE TABLE IF NOT EXISTS `course_catalog_materials` (
  `id` VARCHAR(32) NOT NULL,
  `catalog_id` VARCHAR(32) NOT NULL,
  `filename` VARCHAR(255) NOT NULL,
  `source_type` VARCHAR(30) NOT NULL,
  `storage_uri` VARCHAR(500) DEFAULT NULL,
  `file_size` BIGINT NOT NULL DEFAULT 0,
  `chunk_count` INT NOT NULL DEFAULT 0,
  `last_error` VARCHAR(500) DEFAULT NULL,
  `ingested_at` DATETIME DEFAULT NULL,
  `status` VARCHAR(20) NOT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `catalog_id` (`catalog_id`),
  CONSTRAINT `course_catalog_materials_ibfk_1` FOREIGN KEY (`catalog_id`) REFERENCES `course_catalogs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 课程开班
-- ============================================================
CREATE TABLE IF NOT EXISTS `course_offerings` (
  `id` VARCHAR(32) NOT NULL,
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `catalog_id` VARCHAR(32) NOT NULL,
  `teacher_id` VARCHAR(32) NOT NULL,
  `class_code` VARCHAR(20) NOT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `class_code` (`class_code`),
  KEY `catalog_id` (`catalog_id`),
  KEY `teacher_id` (`teacher_id`),
  CONSTRAINT `course_offerings_ibfk_1` FOREIGN KEY (`catalog_id`) REFERENCES `course_catalogs` (`id`),
  CONSTRAINT `course_offerings_ibfk_2` FOREIGN KEY (`teacher_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 题目
-- ============================================================
CREATE TABLE IF NOT EXISTS `quiz_questions` (
  `id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `catalog_id` VARCHAR(32) DEFAULT NULL,
  `chapter` VARCHAR(100) NOT NULL,
  `knowledge_point` VARCHAR(100) NOT NULL,
  `type` VARCHAR(20) NOT NULL COMMENT 'single_choice/multi_choice/judgment/fill_blank',
  `source` VARCHAR(20) NOT NULL DEFAULT 'system',
  `personalized` TINYINT(1) NOT NULL DEFAULT 0,
  `owner_user_id` VARCHAR(32) DEFAULT NULL,
  `difficulty` VARCHAR(10) NOT NULL,
  `content` TEXT NOT NULL,
  `options` JSON DEFAULT NULL,
  `correct_answer` VARCHAR(500) NOT NULL,
  `explanation` TEXT,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `quiz_questions_ibfk_1` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 答题会话
-- ============================================================
CREATE TABLE IF NOT EXISTS `quiz_sessions` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `chapter` VARCHAR(100) NOT NULL,
  `score` FLOAT NOT NULL DEFAULT 0,
  `correct_count` INT NOT NULL DEFAULT 0,
  `total_count` INT NOT NULL DEFAULT 0,
  `time_spent` INT NOT NULL DEFAULT 0,
  `diagnosis_json` JSON DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `quiz_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `quiz_sessions_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 答题记录
-- ============================================================
CREATE TABLE IF NOT EXISTS `quiz_answers` (
  `id` VARCHAR(32) NOT NULL,
  `quiz_id` VARCHAR(32) NOT NULL,
  `question_id` VARCHAR(32) NOT NULL,
  `user_answer` VARCHAR(500) NOT NULL,
  `is_correct` TINYINT(1) NOT NULL DEFAULT 0,
  `correct_answer` VARCHAR(500) NOT NULL,
  `explanation` TEXT,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `quiz_id` (`quiz_id`),
  KEY `question_id` (`question_id`),
  CONSTRAINT `quiz_answers_ibfk_1` FOREIGN KEY (`quiz_id`) REFERENCES `quiz_sessions` (`id`),
  CONSTRAINT `quiz_answers_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `quiz_questions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- AI 对话会话
-- ============================================================
CREATE TABLE IF NOT EXISTS `conversations` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `scope` VARCHAR(20) NOT NULL,
  `course_id` VARCHAR(32) DEFAULT NULL,
  `title` VARCHAR(200) NOT NULL,
  `summary` TEXT,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `conversations_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `conversations_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- AI 对话消息
-- ============================================================
CREATE TABLE IF NOT EXISTS `messages` (
  `id` VARCHAR(32) NOT NULL,
  `conversation_id` VARCHAR(32) NOT NULL,
  `role` VARCHAR(10) NOT NULL,
  `content` TEXT,
  `diagrams` JSON DEFAULT NULL,
  `knowledge_points` JSON DEFAULT NULL,
  `meta_json` JSON DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `conversation_id` (`conversation_id`),
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 学习资源
-- ============================================================
CREATE TABLE IF NOT EXISTS `resources` (
  `id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `catalog_id` VARCHAR(32) DEFAULT NULL,
  `title` VARCHAR(200) NOT NULL,
  `type` VARCHAR(30) NOT NULL,
  `description` TEXT,
  `tags` JSON DEFAULT NULL,
  `chapter` VARCHAR(100) NOT NULL,
  `knowledge_point` VARCHAR(100) NOT NULL,
  `content` TEXT,
  `url` VARCHAR(500) NOT NULL,
  `view_count` INT NOT NULL DEFAULT 0,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `course_id` (`course_id`),
  KEY `catalog_id` (`catalog_id`),
  CONSTRAINT `resources_ibfk_1` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`),
  CONSTRAINT `resources_ibfk_2` FOREIGN KEY (`catalog_id`) REFERENCES `course_catalogs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 异步任务
-- ============================================================
CREATE TABLE IF NOT EXISTS `async_tasks` (
  `id` VARCHAR(32) NOT NULL,
  `task_type` VARCHAR(30) NOT NULL,
  `status` VARCHAR(20) NOT NULL,
  `progress` INT NOT NULL DEFAULT 0,
  `user_id` VARCHAR(32) DEFAULT NULL,
  `course_id` VARCHAR(32) DEFAULT NULL,
  `result` JSON DEFAULT NULL,
  `error_code` VARCHAR(20) DEFAULT NULL,
  `error_message` VARCHAR(500) NOT NULL DEFAULT '',
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `completed_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `async_tasks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `async_tasks_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 学习效果评估
-- ============================================================
CREATE TABLE IF NOT EXISTS `evaluations` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `progress_table` JSON DEFAULT NULL,
  `mastery_table` JSON DEFAULT NULL,
  `resource_usage_table` JSON DEFAULT NULL,
  `summary_text` TEXT,
  `insight` JSON DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `generated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `evaluations_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `evaluations_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 用户画像
-- ============================================================
CREATE TABLE IF NOT EXISTS `user_profiles` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `modal_preference` JSON DEFAULT NULL,
  `guidance_level_current` VARCHAR(5) NOT NULL DEFAULT 'L2',
  `guidance_level_updated_at` DATETIME DEFAULT NULL,
  `knowledge_mastered` INT NOT NULL DEFAULT 0,
  `knowledge_weak` INT NOT NULL DEFAULT 0,
  `knowledge_coordinates` JSON DEFAULT NULL,
  `cognitive_blindspots` JSON DEFAULT NULL,
  `drive_intent` JSON DEFAULT NULL,
  `discipline_badge` JSON DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `generated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `user_profiles_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `user_profiles_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 学习路径
-- ============================================================
CREATE TABLE IF NOT EXISTS `learning_paths` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `nodes` JSON DEFAULT NULL,
  `edges` JSON DEFAULT NULL,
  `current_node_id` VARCHAR(32) NOT NULL,
  `current_node_name` VARCHAR(100) NOT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `generated_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `course_id` (`course_id`),
  CONSTRAINT `learning_paths_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `learning_paths_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 课程知识图谱
-- ============================================================
CREATE TABLE IF NOT EXISTS `course_knowledge_graphs` (
  `id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `version` INT NOT NULL DEFAULT 1,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `source_type` VARCHAR(40) NOT NULL,
  `generation_strategy` VARCHAR(60) NOT NULL,
  `nodes` JSON NOT NULL,
  `edges` JSON NOT NULL,
  `metrics` JSON DEFAULT NULL,
  `parent_graph_id` VARCHAR(32) DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_course_version` (`course_id`, `version`),
  KEY `idx_parent_graph_id` (`parent_graph_id`),
  KEY `idx_is_deleted` (`is_deleted`),
  KEY `idx_course_active` (`course_id`, `is_active`, `is_deleted`),
  CONSTRAINT `course_knowledge_graphs_ibfk_1` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`),
  CONSTRAINT `fk_ckg_parent_graph` FOREIGN KEY (`parent_graph_id`) REFERENCES `course_knowledge_graphs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 学习活动记录
-- ============================================================
CREATE TABLE IF NOT EXISTS `learning_activities` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `node_id` VARCHAR(64) DEFAULT NULL,
  `node_name` VARCHAR(100) DEFAULT NULL,
  `resource_id` VARCHAR(32) DEFAULT NULL,
  `activity_type` VARCHAR(40) NOT NULL,
  `duration_seconds` INT DEFAULT NULL,
  `occurred_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `metadata` JSON DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `course_id` (`course_id`),
  KEY `idx_learning_activities_user_course_node` (`user_id`, `course_id`, `node_id`, `is_deleted`),
  KEY `idx_learning_activities_type_time` (`user_id`, `course_id`, `activity_type`, `occurred_at`),
  KEY `idx_learning_activities_resource` (`resource_id`, `is_deleted`),
  CONSTRAINT `learning_activities_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `learning_activities_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`),
  CONSTRAINT `learning_activities_ibfk_3` FOREIGN KEY (`resource_id`) REFERENCES `resources` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 个性化资源/题目（AI 生成分发）
-- ============================================================
CREATE TABLE IF NOT EXISTS `code_problems` (
  `id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `owner_user_id` VARCHAR(32) DEFAULT NULL,
  `origin` VARCHAR(30) NOT NULL DEFAULT 'ai_chat',
  `conversation_id` VARCHAR(32) DEFAULT NULL,
  `run_id` VARCHAR(80) DEFAULT NULL,
  `title` VARCHAR(200) NOT NULL,
  `statement` TEXT NOT NULL,
  `chapter` VARCHAR(100) NOT NULL DEFAULT '',
  `knowledge_point` VARCHAR(100) NOT NULL DEFAULT '',
  `difficulty` VARCHAR(10) NOT NULL DEFAULT 'medium',
  `language` VARCHAR(20) NOT NULL,
  `starter_code` TEXT NOT NULL,
  `reference_solution` TEXT NOT NULL,
  `validation_report` JSON NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'validated',
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_code_problems_owner_course` (`owner_user_id`, `course_id`, `is_deleted`),
  KEY `idx_code_problems_conversation` (`conversation_id`, `is_deleted`),
  CONSTRAINT `code_problems_course_fk` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`),
  CONSTRAINT `code_problems_owner_fk` FOREIGN KEY (`owner_user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `code_problems_conversation_fk` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `code_problem_test_cases` (
  `id` VARCHAR(32) NOT NULL,
  `problem_id` VARCHAR(32) NOT NULL,
  `ordinal` INT NOT NULL,
  `stdin` TEXT NOT NULL,
  `expected_output` TEXT NOT NULL,
  `is_public` TINYINT(1) NOT NULL DEFAULT 0,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_code_problem_cases_problem_order` (`problem_id`, `ordinal`),
  CONSTRAINT `code_problem_test_cases_problem_fk` FOREIGN KEY (`problem_id`) REFERENCES `code_problems` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `personalized_resource_generations` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `conversation_id` VARCHAR(32) DEFAULT NULL,
  `run_id` VARCHAR(64) DEFAULT NULL,
  `agent_run_id` VARCHAR(80) DEFAULT NULL,
  `idempotency_key` VARCHAR(64) DEFAULT NULL,
  `source_type` VARCHAR(30) NOT NULL,
  `goal` TEXT NOT NULL,
  `resource_type` VARCHAR(40) NOT NULL,
  `status` VARCHAR(30) NOT NULL DEFAULT 'drafted',
  `draft` JSON NOT NULL,
  `validation_report` JSON DEFAULT NULL,
  `review_decision` VARCHAR(30) DEFAULT NULL,
  `review_report` JSON DEFAULT NULL,
  `artifact_payload` JSON DEFAULT NULL,
  `delivery_error` TEXT,
  `delivery_attempts` INT NOT NULL DEFAULT 0,
  `published_resource_id` VARCHAR(32) DEFAULT NULL,
  `published_code_problem_id` VARCHAR(32) DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prg_idempotency_key` (`idempotency_key`),
  KEY `idx_prg_user_course` (`user_id`, `course_id`, `is_deleted`),
  KEY `idx_prg_status` (`status`, `is_deleted`),
  KEY `published_resource_id` (`published_resource_id`),
  KEY `published_code_problem_id` (`published_code_problem_id`),
  CONSTRAINT `fk_prg_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_prg_course` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`),
  CONSTRAINT `fk_prg_resource` FOREIGN KEY (`published_resource_id`) REFERENCES `resources` (`id`),
  CONSTRAINT `fk_prg_code_problem` FOREIGN KEY (`published_code_problem_id`) REFERENCES `code_problems` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `user_personalized_resources` (
  `id` VARCHAR(32) NOT NULL,
  `user_id` VARCHAR(32) NOT NULL,
  `course_id` VARCHAR(32) NOT NULL,
  `resource_id` VARCHAR(32) DEFAULT NULL,
  `question_id` VARCHAR(32) DEFAULT NULL,
  `code_problem_id` VARCHAR(32) DEFAULT NULL,
  `source_type` VARCHAR(30) NOT NULL,
  `task_id` VARCHAR(32) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `course_id` (`course_id`),
  KEY `resource_id` (`resource_id`),
  KEY `question_id` (`question_id`),
  KEY `code_problem_id` (`code_problem_id`),
  KEY `idx_upr_user_course` (`user_id`, `course_id`, `is_deleted`),
  KEY `idx_upr_task` (`task_id`),
  CONSTRAINT `user_personalized_resources_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `user_personalized_resources_ibfk_2` FOREIGN KEY (`course_id`) REFERENCES `courses` (`id`),
  CONSTRAINT `user_personalized_resources_ibfk_3` FOREIGN KEY (`resource_id`) REFERENCES `resources` (`id`),
  CONSTRAINT `user_personalized_resources_ibfk_4` FOREIGN KEY (`question_id`) REFERENCES `quiz_questions` (`id`),
  CONSTRAINT `user_personalized_resources_code_problem_fk` FOREIGN KEY (`code_problem_id`) REFERENCES `code_problems` (`id`),
  CONSTRAINT `user_personalized_resources_ibfk_5` FOREIGN KEY (`task_id`) REFERENCES `async_tasks` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- Agent 日志（从 agent_service 写回）
-- ============================================================
CREATE TABLE IF NOT EXISTS `agent_logs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `agent_type` VARCHAR(20) NOT NULL,
  `endpoint` VARCHAR(200) NOT NULL,
  `latency_ms` INT NOT NULL DEFAULT 0,
  `tokens_used` INT NOT NULL DEFAULT 0,
  `status` VARCHAR(10) NOT NULL,
  `error_message` VARCHAR(500) DEFAULT NULL,
  `security_blocked` TINYINT(1) NOT NULL DEFAULT 0,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ============================================================
-- 操作日志
-- ============================================================
CREATE TABLE IF NOT EXISTS `operation_logs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `event_type` VARCHAR(30) NOT NULL,
  `user_id` VARCHAR(32) DEFAULT NULL,
  `description` VARCHAR(300) NOT NULL,
  `ip_address` VARCHAR(45) NOT NULL DEFAULT '',
  `detail` JSON DEFAULT NULL,
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `create_by` VARCHAR(32) DEFAULT NULL,
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `update_by` VARCHAR(32) DEFAULT NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
