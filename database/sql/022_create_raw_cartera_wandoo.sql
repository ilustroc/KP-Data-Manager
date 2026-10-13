-- KP Data Manager - Carteras / Wandoo v1
-- MySQL 5.7.33 compatible. Revisión y ejecución manual obligatorias.
-- Preserva las 19 posiciones fuente; row_hash es una huella técnica NO UNIQUE.

CREATE TABLE `kp_bronze`.`raw_cartera_wandoo` (
    `dni` VARCHAR(100) NULL,
    `numero_prestamo` VARCHAR(100) NULL,
    `recuento_prestamos_pagados` VARCHAR(100) NULL,
    `nacionalidad` VARCHAR(100) NULL,
    `saldo_deudor` VARCHAR(100) NULL,
    `fecha_ultimo_pago` VARCHAR(100) NULL,
    `total_soles_pagados` VARCHAR(100) NULL,
    `departamento` VARCHAR(255) NULL,
    `provincia` VARCHAR(255) NULL,
    `distrito` VARCHAR(255) NULL,
    `edad` VARCHAR(100) NULL,
    `dias_mora` VARCHAR(100) NULL,
    `producto_crediticio` VARCHAR(255) NULL,
    `fuente_ingreso` VARCHAR(255) NULL,
    `estado_cobranza_actual` VARCHAR(255) NULL,
    `contactabilidad_interna` VARCHAR(100) NULL,
    `fecha_otorgamiento_credito` VARCHAR(100) NULL,
    `actividad_laboral` VARCHAR(255) NULL,
    `cosecha` VARCHAR(100) NULL,
    `raw_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_row` BIGINT UNSIGNED NOT NULL,
    `source_file` VARCHAR(255) NOT NULL,
    `row_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `ingested_at` DATETIME NOT NULL,
    PRIMARY KEY (`raw_id`),
    KEY `idx_raw_cartera_wandoo_batch_row` (`batch_id`, `source_row`),
    KEY `idx_raw_cartera_wandoo_row_hash` (`row_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
