-- DM-F6: Silver histórico FAMILIA. Compatible con MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_familiares` (
    `family_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `documento_familiar` VARCHAR(100) NULL,
    `paterno_familiar` VARCHAR(255) NULL,
    `materno_familiar` VARCHAR(255) NULL,
    `nombres_familiar` VARCHAR(255) NULL,
    `nacimiento_familiar` VARCHAR(100) NULL,
    `tipo_familiar` VARCHAR(100) NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_row_number` INT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`family_id`),
    UNIQUE KEY `uq_search_familiares_batch_source_row` (`batch_id`, `source_row_number`),
    KEY `idx_search_familiares_document_batch` (`documento`, `batch_id`),
    KEY `idx_search_familiares_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_familiares_source_raw` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
