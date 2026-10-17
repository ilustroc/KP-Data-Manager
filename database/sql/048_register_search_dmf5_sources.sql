-- DM-F5: registro manual e idempotente de fuentes SEARCH. MySQL 5.7.33.
INSERT INTO `kp_control`.`import_source` (`source_code`, `label`, `description`, `is_active`, `created_at`, `updated_at`) VALUES
('BASE_SBS', 'Base SBS resumen', 'Procedencia estable de SBS resumen SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
('BASE_SBS_DETALLE', 'Base SBS detalle', 'Procedencia estable de SBS detalle SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
('BASE_ESSALUD', 'Base EsSalud', 'Procedencia estable de empleo EsSalud SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE `label` = VALUES(`label`), `description` = VALUES(`description`), `is_active` = VALUES(`is_active`), `updated_at` = VALUES(`updated_at`);

INSERT INTO `kp_control`.`import_dataset_source` (`dataset_code`, `source_code`, `default_refresh_mode`, `allows_full_replace`, `allows_scope_replace`, `allows_upsert`, `current_mapping_version`, `is_active`, `created_at`, `updated_at`) VALUES
('SBS_RESUMEN', 'BASE_SBS', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
('SBS_DETALLE', 'BASE_SBS_DETALLE', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
('LABORAL_ESSALUD', 'BASE_ESSALUD', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE `default_refresh_mode` = VALUES(`default_refresh_mode`), `allows_full_replace` = VALUES(`allows_full_replace`), `allows_scope_replace` = VALUES(`allows_scope_replace`), `allows_upsert` = VALUES(`allows_upsert`), `is_active` = VALUES(`is_active`), `updated_at` = VALUES(`updated_at`);
