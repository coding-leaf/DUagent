ALTER TABLE course_catalogs
    ADD COLUMN kg_host_course_id VARCHAR(32) NULL AFTER last_error,
    ADD INDEX idx_course_catalog_kg_host_course_id (kg_host_course_id),
    ADD CONSTRAINT fk_course_catalog_kg_host_course
        FOREIGN KEY (kg_host_course_id) REFERENCES courses(id);
