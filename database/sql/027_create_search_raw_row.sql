-- KP Data Manager - DM-F1 / landing RAW genérico SEARCH
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- Tabla append-only: row_hash es una huella técnica NO UNIQUE.

CREATE TABLE `kp_bronze`.`search_raw_row` (
    `raw_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `dataset_code` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_row` BIGINT UNSIGNED NOT NULL,
    `source_file` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
    `raw_payload` JSON NOT NULL,
    `row_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `ingested_at` DATETIME NOT NULL,
    PRIMARY KEY (`raw_id`),
    KEY `idx_search_raw_row_batch_row` (`batch_id`, `source_row`),
    KEY `idx_search_raw_row_dataset_source_batch` (`dataset_code`, `source_code`, `batch_id`),
    KEY `idx_search_raw_row_hash` (`row_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
