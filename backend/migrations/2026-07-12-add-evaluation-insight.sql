ALTER TABLE evaluations
    ADD COLUMN insight JSON NULL AFTER summary_text;
