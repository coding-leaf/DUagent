ALTER TABLE personalized_resource_generations
    ADD COLUMN published_code_problem_id VARCHAR(32) NULL AFTER published_resource_id,
    ADD CONSTRAINT fk_prg_code_problem
        FOREIGN KEY (published_code_problem_id) REFERENCES code_problems(id);
