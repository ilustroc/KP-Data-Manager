-- KP Data Manager - DM-F4 / Gold PROPIEDADES actual. MySQL 5.7.33.
CREATE TABLE `kp_gold`.`search_propiedades` (
    `property_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `partida_registral` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `zona_registral` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `oficina` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`property_id`),
    UNIQUE KEY `uq_search_propiedades_document_record` (`documento`, `record_hash`),
    KEY `idx_search_propiedades_document_order` (`documento`, `oficina`, `partida_registral`),
    KEY `idx_search_propiedades_source_batch` (`source_code`, `batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
