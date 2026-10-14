-- KP Data Manager - DM-F1 / catálogos SEARCH
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- Crea catálogos nuevos; no modifica PAGOS, CARTERA, Bronze, Silver ni Gold existentes.

CREATE TABLE `kp_control`.`import_dataset` (
    `dataset_code` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `label` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `description` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    `sort_order` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`dataset_code`),
    KEY `idx_import_dataset_active_order` (`is_active`, `sort_order`, `dataset_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_control`.`import_source` (
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `label` VARCHAR(150) COLLATE utf8mb4_unicode_ci NOT NULL,
    `description` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`source_code`),
    KEY `idx_import_source_active_label` (`is_active`, `label`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_control`.`import_dataset_source` (
    `dataset_code` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `default_refresh_mode` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `allows_full_replace` TINYINT(1) NOT NULL DEFAULT 0,
    `allows_scope_replace` TINYINT(1) NOT NULL DEFAULT 0,
    `allows_upsert` TINYINT(1) NOT NULL DEFAULT 0,
    `current_mapping_version` INT UNSIGNED NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`dataset_code`, `source_code`),
    KEY `idx_import_dataset_source_source` (`source_code`, `is_active`),
    KEY `idx_import_dataset_source_active` (`dataset_code`, `is_active`, `source_code`),
    CONSTRAINT `fk_import_dataset_source_dataset`
        FOREIGN KEY (`dataset_code`) REFERENCES `kp_control`.`import_dataset` (`dataset_code`)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT `fk_import_dataset_source_source`
        FOREIGN KEY (`source_code`) REFERENCES `kp_control`.`import_source` (`source_code`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `kp_control`.`import_dataset`
    (`dataset_code`, `label`, `description`, `sort_order`, `is_active`, `created_at`, `updated_at`)
VALUES
    ('PERSONAS', 'Personas', 'Identidad y datos generales de personas.', 10, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('TELEFONOS', 'Teléfonos', 'Teléfonos asociados a personas.', 20, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('FAMILIA', 'Familia', 'Relaciones familiares.', 30, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('DIRECCIONES', 'Direcciones', 'Direcciones asociadas a personas.', 40, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('LABORAL_ESSALUD', 'Laboral EsSalud', 'Información laboral proveniente de EsSalud.', 50, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('VEHICULOS', 'Vehículos', 'Vehículos asociados a personas.', 60, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CORREOS', 'Correos', 'Correos electrónicos asociados a personas.', 70, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('SUNAT', 'SUNAT', 'Información tributaria publicada para búsqueda.', 80, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('SBS_RESUMEN', 'SBS resumen', 'Resumen de información SBS.', 90, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('SBS_DETALLE', 'SBS detalle', 'Detalle de información SBS.', 100, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('PROPIEDADES', 'Propiedades', 'Propiedades asociadas a personas.', 110, 1, UTC_TIMESTAMP(), UTC_TIMESTAMP());
