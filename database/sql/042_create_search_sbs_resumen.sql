-- DM-F5: Silver histórico SBS RESUMEN. Compatible con MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_sbs_resumen` (
    `summary_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cod_sbs` CHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `fecha_reporte_sbs` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cantidad_empresas` INT UNSIGNED NOT NULL,
    `calificacion_normal` DECIMAL(7,4) NULL,
    `calificacion_cpp` DECIMAL(7,4) NULL,
    `calificacion_deficiente` DECIMAL(7,4) NULL,
    `calificacion_dudoso` DECIMAL(7,4) NULL,
    `calificacion_perdida` DECIMAL(7,4) NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`summary_id`),
    UNIQUE KEY `uq_sbs_summary_batch_identity` (`batch_id`, `documento`, `fecha_reporte_sbs`, `cod_sbs`),
    KEY `idx_sbs_summary_document` (`documento`),
    KEY `idx_sbs_summary_document_period` (`documento`, `fecha_reporte_sbs`),
    KEY `idx_sbs_summary_source_batch` (`source_code`, `batch_id`),
    KEY `idx_sbs_summary_source_raw` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
