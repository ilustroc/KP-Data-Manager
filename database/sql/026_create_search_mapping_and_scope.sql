-- KP Data Manager - DM-F1 / mapping y scope oficial de SEARCH
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- No crea tablas Silver ni Gold.

CREATE TABLE `kp_control`.`import_column_mapping` (
    `mapping_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `dataset_code` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `mapping_version` INT UNSIGNED NOT NULL,
    `source_position` SMALLINT UNSIGNED NOT NULL,
    `source_column` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
    `target_column` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `is_required` TINYINT(1) NOT NULL DEFAULT 0,
    `transformation` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_general_ci NULL,
    `default_value` TEXT COLLATE utf8mb4_unicode_ci NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`mapping_id`),
    UNIQUE KEY `uq_import_column_mapping_position`
        (`dataset_code`, `source_code`, `mapping_version`, `source_position`),
    UNIQUE KEY `uq_import_column_mapping_target`
        (`dataset_code`, `source_code`, `mapping_version`, `target_column`),
    KEY `idx_import_column_mapping_lookup`
        (`dataset_code`, `source_code`, `mapping_version`, `is_active`, `source_position`),
    CONSTRAINT `fk_import_column_mapping_dataset_source`
        FOREIGN KEY (`dataset_code`, `source_code`)
        REFERENCES `kp_control`.`import_dataset_source` (`dataset_code`, `source_code`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_control`.`import_scope_document` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `documento` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_import_scope_document_batch` (`batch_id`, `documento`),
    KEY `idx_import_scope_document_lookup` (`documento`, `batch_id`),
    CONSTRAINT `fk_import_scope_document_batch`
        FOREIGN KEY (`batch_id`) REFERENCES `kp_control`.`import_batch` (`batch_id`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
