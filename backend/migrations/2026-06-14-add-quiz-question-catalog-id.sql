ALTER TABLE quiz_questions ADD COLUMN catalog_id VARCHAR(32) DEFAULT NULL;
CREATE INDEX idx_quiz_catalog ON quiz_questions(catalog_id, is_deleted);
