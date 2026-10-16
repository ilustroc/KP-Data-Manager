-- KP Data Manager - DM-F4 / Gold CORREOS actual. MySQL 5.7.33.
CREATE TABLE `kp_gold`.`search_correos` (
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `correo` VARCHAR(254) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    `correo_original` VARCHAR(320) COLLATE utf8mb4_unicode_ci NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`documento`, `correo`),
    KEY `idx_search_correos_source_batch` (`source_code`, `batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
