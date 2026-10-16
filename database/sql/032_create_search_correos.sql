-- KP Data Manager - DM-F4 / Silver histórico CORREOS. MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_correos` (
    `email_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `correo` VARCHAR(254) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    `correo_original` VARCHAR(320) COLLATE utf8mb4_unicode_ci NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`email_id`),
    UNIQUE KEY `uq_search_correos_batch_document_email` (`batch_id`, `documento`, `correo`),
    KEY `idx_search_correos_document` (`documento`),
    KEY `idx_search_correos_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_correos_source_raw` (`source_raw_id`),
    KEY `idx_search_correos_record_hash` (`record_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
