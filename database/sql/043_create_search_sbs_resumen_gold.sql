-- DM-F5: Gold vigente SBS RESUMEN. Compatible con MySQL 5.7.33.
CREATE TABLE `kp_gold`.`search_sbs_resumen` (
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
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`documento`, `fecha_reporte_sbs`, `cod_sbs`),
    KEY `idx_sbs_resumen_source_batch` (`source_code`, `batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
