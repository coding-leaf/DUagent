ALTER TABLE personalized_resource_generations
    ADD COLUMN agent_run_id VARCHAR(80) NULL AFTER run_id,
    ADD COLUMN idempotency_key VARCHAR(64) NULL AFTER agent_run_id,
    ADD COLUMN artifact_payload JSON NULL AFTER review_report,
    ADD COLUMN delivery_error TEXT NULL AFTER artifact_payload,
    ADD COLUMN delivery_attempts INT NOT NULL DEFAULT 0 AFTER delivery_error,
    ADD UNIQUE INDEX uk_prg_idempotency_key (idempotency_key);
