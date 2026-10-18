-- DM-F5: Silver histórico SBS DETALLE. Compatible con MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_sbs_detalle` (
    `detail_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `fecha_reporte_sbs` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `documento` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cod_sbs` CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `entidad` VARCHAR(255) NULL,
    `tipo_credito` VARCHAR(500) NULL,
    `condicion` VARCHAR(8) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `monto` DECIMAL(18,2) NULL,
    `dias_atraso` INT UNSIGNED NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`detail_id`),
    UNIQUE KEY `uq_sbs_detail_batch_hash` (`batch_id`, `record_hash`),
    KEY `idx_sbs_detail_document_period` (`documento`, `fecha_reporte_sbs`),
    KEY `idx_sbs_detail_document_entity` (`documento`, `entidad`),
    KEY `idx_sbs_detail_source_batch` (`source_code`, `batch_id`),
    KEY `idx_sbs_detail_source_raw` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
