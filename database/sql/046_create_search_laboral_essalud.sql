-- DM-F5: Silver histórico LABORAL ESSALUD. Compatible con MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_laboral_essalud` (
    `employment_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `periodo` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `ruc` CHAR(11) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `nombre_empresa` VARCHAR(255) NULL,
    `sueldo` DECIMAL(18,2) NULL,
    `situacion` VARCHAR(20) NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`employment_id`),
    UNIQUE KEY `uq_essalud_batch_hash` (`batch_id`, `record_hash`),
    KEY `idx_essalud_document_period` (`documento`, `periodo`),
    KEY `idx_essalud_document_ruc` (`documento`, `ruc`),
    KEY `idx_essalud_source_batch` (`source_code`, `batch_id`),
    KEY `idx_essalud_source_raw` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
