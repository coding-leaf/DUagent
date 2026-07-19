-- Extend CourseCatalog ingestion state for existing MySQL databases.
-- Fresh deployments may already get these columns from 2026-06-07-add-course-catalogs.sql.

SET @add_catalog_last_ingestion_task_id = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalogs ADD COLUMN last_ingestion_task_id VARCHAR(32) DEFAULT NULL AFTER material_count',
        'SELECT ''course_catalogs.last_ingestion_task_id already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalogs'
      AND column_name = 'last_ingestion_task_id'
);
PREPARE stmt FROM @add_catalog_last_ingestion_task_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_catalog_last_ingestion_status = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalogs ADD COLUMN last_ingestion_status VARCHAR(20) DEFAULT NULL AFTER last_ingestion_task_id',
        'SELECT ''course_catalogs.last_ingestion_status already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalogs'
      AND column_name = 'last_ingestion_status'
);
PREPARE stmt FROM @add_catalog_last_ingestion_status;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_catalog_chunk_count = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalogs ADD COLUMN chunk_count INT NOT NULL DEFAULT 0 AFTER last_ingestion_status',
        'SELECT ''course_catalogs.chunk_count already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalogs'
      AND column_name = 'chunk_count'
);
PREPARE stmt FROM @add_catalog_chunk_count;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_catalog_last_error = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalogs ADD COLUMN last_error VARCHAR(500) DEFAULT NULL AFTER chunk_count',
        'SELECT ''course_catalogs.last_error already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalogs'
      AND column_name = 'last_error'
);
PREPARE stmt FROM @add_catalog_last_error;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_material_file_size = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalog_materials ADD COLUMN file_size BIGINT NOT NULL DEFAULT 0 AFTER storage_uri',
        'SELECT ''course_catalog_materials.file_size already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalog_materials'
      AND column_name = 'file_size'
);
PREPARE stmt FROM @add_material_file_size;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_material_chunk_count = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalog_materials ADD COLUMN chunk_count INT NOT NULL DEFAULT 0 AFTER file_size',
        'SELECT ''course_catalog_materials.chunk_count already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalog_materials'
      AND column_name = 'chunk_count'
);
PREPARE stmt FROM @add_material_chunk_count;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_material_last_error = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalog_materials ADD COLUMN last_error VARCHAR(500) DEFAULT NULL AFTER chunk_count',
        'SELECT ''course_catalog_materials.last_error already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalog_materials'
      AND column_name = 'last_error'
);
PREPARE stmt FROM @add_material_last_error;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_material_ingested_at = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_catalog_materials ADD COLUMN ingested_at DATETIME DEFAULT NULL AFTER last_error',
        'SELECT ''course_catalog_materials.ingested_at already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_catalog_materials'
      AND column_name = 'ingested_at'
);
PREPARE stmt FROM @add_material_ingested_at;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
