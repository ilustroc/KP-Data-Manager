-- DM-F5: Gold vigente SBS DETALLE. Compatible con MySQL 5.7.33.
CREATE TABLE `kp_gold`.`search_sbs_detalle` (
    `gold_detail_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `fecha_reporte_sbs` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `documento` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cod_sbs` CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `entidad` VARCHAR(255) NULL,
    `tipo_credito` VARCHAR(500) NULL,
    `condicion` VARCHAR(8) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `monto` DECIMAL(18,2) NULL,
    `dias_atraso` INT UNSIGNED NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`gold_detail_id`),
    UNIQUE KEY `uq_gold_sbs_detail_document_hash` (`documento`, `record_hash`),
    KEY `idx_gold_sbs_detail_document_period` (`documento`, `fecha_reporte_sbs`),
    KEY `idx_gold_sbs_detail_source_batch` (`source_code`, `batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
