-- DM-F6: registro manual e idempotente de fuente SEARCH. Compatible con MySQL 5.7.33.
INSERT INTO `kp_control`.`import_source`
    (`source_code`, `label`, `description`, `is_active`, `created_at`, `updated_at`)
VALUES
    ('BASE_FAMILIA', 'Base Familia', 'Procedencia estable de relaciones familiares SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE
    `label` = VALUES(`label`),
    `description` = VALUES(`description`),
    `is_active` = VALUES(`is_active`),
    `updated_at` = VALUES(`updated_at`);

INSERT INTO `kp_control`.`import_dataset_source`
    (`dataset_code`, `source_code`, `default_refresh_mode`, `allows_full_replace`, `allows_scope_replace`, `allows_upsert`, `current_mapping_version`, `is_active`, `created_at`, `updated_at`)
VALUES
    ('FAMILIA', 'BASE_FAMILIA', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE
    `default_refresh_mode` = VALUES(`default_refresh_mode`),
    `allows_full_replace` = VALUES(`allows_full_replace`),
    `allows_scope_replace` = VALUES(`allows_scope_replace`),
    `allows_upsert` = VALUES(`allows_upsert`),
    `is_active` = VALUES(`is_active`),
    `updated_at` = VALUES(`updated_at`);
