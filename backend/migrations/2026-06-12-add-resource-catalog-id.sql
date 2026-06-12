ALTER TABLE resources
    ADD COLUMN catalog_id VARCHAR(32) NULL AFTER course_id,
    ADD INDEX idx_resource_catalog_id (catalog_id),
    ADD CONSTRAINT fk_resource_catalog
        FOREIGN KEY (catalog_id) REFERENCES course_catalogs(id);
