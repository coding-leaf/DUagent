CREATE TABLE IF NOT EXISTS course_catalogs (
    id VARCHAR(32) PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    knowledge_status VARCHAR(20) NOT NULL DEFAULT 'draft',
    material_count INT NOT NULL DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_course_catalog_status (status),
    INDEX idx_course_catalog_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='平台共享课程资源库';

CREATE TABLE IF NOT EXISTS course_catalog_materials (
    id VARCHAR(32) PRIMARY KEY,
    catalog_id VARCHAR(32) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    source_type VARCHAR(30) NOT NULL,
    storage_uri VARCHAR(500) DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'uploaded',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_catalog_material_catalog (catalog_id),
    INDEX idx_catalog_material_deleted (is_deleted),
    CONSTRAINT fk_catalog_material_catalog FOREIGN KEY (catalog_id) REFERENCES course_catalogs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='课程资源库原始资料';

CREATE TABLE IF NOT EXISTS course_offerings (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT DEFAULT NULL,
    catalog_id VARCHAR(32) NOT NULL,
    teacher_id VARCHAR(32) NOT NULL,
    class_code VARCHAR(20) NOT NULL UNIQUE,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_course_offering_catalog (catalog_id),
    INDEX idx_course_offering_teacher (teacher_id),
    INDEX idx_course_offering_deleted (is_deleted),
    CONSTRAINT fk_course_offering_catalog FOREIGN KEY (catalog_id) REFERENCES course_catalogs(id),
    CONSTRAINT fk_course_offering_teacher FOREIGN KEY (teacher_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='教师教学班，绑定平台共享课程资源库';
