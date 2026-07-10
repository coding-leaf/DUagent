CREATE TABLE IF NOT EXISTS code_problems (
  id VARCHAR(32) NOT NULL PRIMARY KEY,
  course_id VARCHAR(32) NOT NULL,
  owner_user_id VARCHAR(32) NULL,
  origin VARCHAR(30) NOT NULL DEFAULT 'ai_chat',
  conversation_id VARCHAR(32) NULL,
  run_id VARCHAR(80) NULL,
  title VARCHAR(200) NOT NULL,
  statement TEXT NOT NULL,
  chapter VARCHAR(100) NOT NULL DEFAULT '',
  knowledge_point VARCHAR(100) NOT NULL DEFAULT '',
  difficulty VARCHAR(10) NOT NULL DEFAULT 'medium',
  language VARCHAR(20) NOT NULL,
  starter_code TEXT NOT NULL,
  reference_solution TEXT NOT NULL,
  validation_report JSON NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'validated',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  create_by VARCHAR(32) NULL,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  update_by VARCHAR(32) NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT code_problems_course_fk FOREIGN KEY (course_id) REFERENCES courses(id),
  CONSTRAINT code_problems_owner_fk FOREIGN KEY (owner_user_id) REFERENCES users(id),
  CONSTRAINT code_problems_conversation_fk FOREIGN KEY (conversation_id) REFERENCES conversations(id),
  INDEX idx_code_problems_owner_course (owner_user_id, course_id, is_deleted),
  INDEX idx_code_problems_conversation (conversation_id, is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS code_problem_test_cases (
  id VARCHAR(32) NOT NULL PRIMARY KEY,
  problem_id VARCHAR(32) NOT NULL,
  ordinal INT NOT NULL,
  stdin TEXT NOT NULL,
  expected_output TEXT NOT NULL,
  is_public BOOLEAN NOT NULL DEFAULT FALSE,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT code_problem_test_cases_problem_fk FOREIGN KEY (problem_id) REFERENCES code_problems(id),
  INDEX idx_code_problem_cases_problem_order (problem_id, ordinal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @column_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'user_personalized_resources' AND column_name = 'code_problem_id'
);
SET @add_column_sql := IF(
  @column_exists = 0,
  'ALTER TABLE user_personalized_resources ADD COLUMN code_problem_id VARCHAR(32) NULL AFTER question_id',
  'SELECT 1'
);
PREPARE add_column_statement FROM @add_column_sql;
EXECUTE add_column_statement;
DEALLOCATE PREPARE add_column_statement;

SET @index_exists := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE() AND table_name = 'user_personalized_resources' AND index_name = 'idx_upr_code_problem'
);
SET @add_index_sql := IF(
  @index_exists = 0,
  'ALTER TABLE user_personalized_resources ADD INDEX idx_upr_code_problem (code_problem_id)',
  'SELECT 1'
);
PREPARE add_index_statement FROM @add_index_sql;
EXECUTE add_index_statement;
DEALLOCATE PREPARE add_index_statement;

SET @constraint_exists := (
  SELECT COUNT(*) FROM information_schema.table_constraints
  WHERE table_schema = DATABASE() AND table_name = 'user_personalized_resources' AND constraint_name = 'user_personalized_resources_code_problem_fk'
);
SET @add_constraint_sql := IF(
  @constraint_exists = 0,
  'ALTER TABLE user_personalized_resources ADD CONSTRAINT user_personalized_resources_code_problem_fk FOREIGN KEY (code_problem_id) REFERENCES code_problems(id)',
  'SELECT 1'
);
PREPARE add_constraint_statement FROM @add_constraint_sql;
EXECUTE add_constraint_statement;
DEALLOCATE PREPARE add_constraint_statement;
