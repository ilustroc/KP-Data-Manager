-- DM-F4: ejecutar manualmente DESPUÉS de 032-039. Idempotente en MySQL 5.7.33.
INSERT INTO `kp_control`.`import_source`
    (`source_code`, `label`, `description`, `is_active`, `created_at`, `updated_at`)
VALUES
    ('BASE_CORREOS', 'Base Correos', 'Procedencia estable de correos SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BASE_DIRECCIONES', 'Base Direcciones', 'Procedencia estable de direcciones SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BASE_VEHICULOS', 'Base Vehículos', 'Procedencia estable de vehículos SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BASE_SUNARP', 'Base SUNARP', 'Procedencia estable de propiedades SEARCH.', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE
    `label` = VALUES(`label`),
    `description` = VALUES(`description`),
    `is_active` = VALUES(`is_active`),
    `updated_at` = VALUES(`updated_at`);

INSERT INTO `kp_control`.`import_dataset_source`
    (`dataset_code`, `source_code`, `default_refresh_mode`, `allows_full_replace`, `allows_scope_replace`, `allows_upsert`, `current_mapping_version`, `is_active`, `created_at`, `updated_at`)
VALUES
    ('CORREOS', 'BASE_CORREOS', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('DIRECCIONES', 'BASE_DIRECCIONES', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('VEHICULOS', 'BASE_VEHICULOS', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('PROPIEDADES', 'BASE_SUNARP', 'FULL_REPLACE', 1, 1, 0, NULL, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE
    `default_refresh_mode` = VALUES(`default_refresh_mode`),
    `allows_full_replace` = VALUES(`allows_full_replace`),
    `allows_scope_replace` = VALUES(`allows_scope_replace`),
    `allows_upsert` = VALUES(`allows_upsert`),
    `is_active` = VALUES(`is_active`),
    `updated_at` = VALUES(`updated_at`);
