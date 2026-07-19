-- Version course_knowledge_graphs for existing MySQL databases.
-- Fresh deployments get the same structure from schema.sql.

SET @drop_ckg_uk_course = (
    SELECT IF(
        COUNT(*) > 0,
        'ALTER TABLE course_knowledge_graphs DROP INDEX uk_course',
        'SELECT ''course_knowledge_graphs.uk_course already absent'' AS migration_status'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND index_name = 'uk_course'
);
PREPARE stmt FROM @drop_ckg_uk_course;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_version = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER course_id',
        'SELECT ''course_knowledge_graphs.version already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND column_name = 'version'
);
PREPARE stmt FROM @add_ckg_version;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_is_active = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER version',
        'SELECT ''course_knowledge_graphs.is_active already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND column_name = 'is_active'
);
PREPARE stmt FROM @add_ckg_is_active;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_source_type = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD COLUMN source_type VARCHAR(40) NOT NULL DEFAULT ''manual_import'' AFTER is_active',
        'SELECT ''course_knowledge_graphs.source_type already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND column_name = 'source_type'
);
PREPARE stmt FROM @add_ckg_source_type;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_generation_strategy = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD COLUMN generation_strategy VARCHAR(60) NOT NULL DEFAULT ''legacy_outline'' AFTER source_type',
        'SELECT ''course_knowledge_graphs.generation_strategy already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND column_name = 'generation_strategy'
);
PREPARE stmt FROM @add_ckg_generation_strategy;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_metrics = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD COLUMN metrics JSON DEFAULT NULL AFTER edges',
        'SELECT ''course_knowledge_graphs.metrics already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND column_name = 'metrics'
);
PREPARE stmt FROM @add_ckg_metrics;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_parent_graph_id = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD COLUMN parent_graph_id VARCHAR(32) DEFAULT NULL AFTER metrics',
        'SELECT ''course_knowledge_graphs.parent_graph_id already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND column_name = 'parent_graph_id'
);
PREPARE stmt FROM @add_ckg_parent_graph_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_uk_course_version = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD UNIQUE INDEX uk_course_version (course_id, version)',
        'SELECT ''course_knowledge_graphs.uk_course_version already exists'' AS migration_status'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND index_name = 'uk_course_version'
);
PREPARE stmt FROM @add_ckg_uk_course_version;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_idx_course_active = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD INDEX idx_course_active (course_id, is_active, is_deleted)',
        'SELECT ''course_knowledge_graphs.idx_course_active already exists'' AS migration_status'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND index_name = 'idx_course_active'
);
PREPARE stmt FROM @add_ckg_idx_course_active;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_idx_parent_graph_id = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD INDEX idx_parent_graph_id (parent_graph_id)',
        'SELECT ''course_knowledge_graphs.idx_parent_graph_id already exists'' AS migration_status'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND index_name = 'idx_parent_graph_id'
);
PREPARE stmt FROM @add_ckg_idx_parent_graph_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_ckg_parent_fk = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE course_knowledge_graphs ADD CONSTRAINT fk_ckg_parent_graph FOREIGN KEY (parent_graph_id) REFERENCES course_knowledge_graphs(id)',
        'SELECT ''course_knowledge_graphs.fk_ckg_parent_graph already exists'' AS migration_status'
    )
    FROM information_schema.table_constraints
    WHERE table_schema = DATABASE()
      AND table_name = 'course_knowledge_graphs'
      AND constraint_name = 'fk_ckg_parent_graph'
);
PREPARE stmt FROM @add_ckg_parent_fk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
