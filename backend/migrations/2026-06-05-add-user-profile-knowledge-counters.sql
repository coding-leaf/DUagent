-- Add internal UserProfile knowledge counters for existing MySQL databases.
-- New deployments get these columns from backend/schema.sql.

SET @add_knowledge_mastered = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE user_profiles ADD COLUMN knowledge_mastered INT NOT NULL DEFAULT 0 AFTER guidance_level_updated_at',
        'SELECT ''knowledge_mastered already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'user_profiles'
      AND column_name = 'knowledge_mastered'
);

PREPARE stmt FROM @add_knowledge_mastered;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_knowledge_weak = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE user_profiles ADD COLUMN knowledge_weak INT NOT NULL DEFAULT 0 AFTER knowledge_mastered',
        'SELECT ''knowledge_weak already exists'' AS migration_status'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'user_profiles'
      AND column_name = 'knowledge_weak'
);

PREPARE stmt FROM @add_knowledge_weak;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
