-- KP Data Manager - DM-F4 / Gold DIRECCIONES actual. MySQL 5.7.33.
CREATE TABLE `kp_gold`.`search_direcciones` (
    `address_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `direccion` VARCHAR(1000) COLLATE utf8mb4_unicode_ci NULL,
    `departamento` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `provincia` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `distrito` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `data_procedencia` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `procedencia_anio` SMALLINT UNSIGNED NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`address_id`),
    UNIQUE KEY `uq_search_direcciones_document_record` (`documento`, `record_hash`),
    KEY `idx_search_direcciones_document_order` (`documento`, `procedencia_anio`, `data_procedencia`),
    KEY `idx_search_direcciones_source_batch` (`source_code`, `batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
