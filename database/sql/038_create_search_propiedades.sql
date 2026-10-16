-- KP Data Manager - DM-F4 / Silver histórico PROPIEDADES. MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_propiedades` (
    `property_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `partida_registral` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `zona_registral` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `oficina` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`property_id`),
    UNIQUE KEY `uq_search_propiedades_batch_record` (`batch_id`, `record_hash`),
    KEY `idx_search_propiedades_document_batch` (`documento`, `batch_id`),
    KEY `idx_search_propiedades_document_partida` (`documento`, `partida_registral`),
    KEY `idx_search_propiedades_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_propiedades_source_raw` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
