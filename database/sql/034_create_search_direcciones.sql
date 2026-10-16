-- KP Data Manager - DM-F4 / Silver histórico DIRECCIONES. MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_direcciones` (
    `address_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `direccion` VARCHAR(1000) COLLATE utf8mb4_unicode_ci NULL,
    `departamento` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `provincia` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `distrito` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `data_procedencia` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `procedencia_anio` SMALLINT UNSIGNED NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`address_id`),
    UNIQUE KEY `uq_search_direcciones_batch_record` (`batch_id`, `record_hash`),
    KEY `idx_search_direcciones_document_batch` (`documento`, `batch_id`),
    KEY `idx_search_direcciones_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_direcciones_source_raw` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
