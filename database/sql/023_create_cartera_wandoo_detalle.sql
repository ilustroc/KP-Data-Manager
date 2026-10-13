-- KP Data Manager - detalle Silver Wandoo v1
-- MySQL 5.7.33 compatible. Revisión y ejecución manual obligatorias.
-- No define UNIQUE de negocio ni claves foráneas entre esquemas.

CREATE TABLE `kp_silver`.`cartera_wandoo_detalle` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `recuento_prestamos_pagados` INT NULL,
    `nacionalidad` VARCHAR(100) NULL,
    `saldo_deudor` DECIMAL(15,2) NULL,
    `fecha_ultimo_pago` DATE NULL,
    `total_soles_pagados` DECIMAL(15,2) NULL,
    `edad` INT NULL,
    `dias_mora` INT NULL,
    `producto_crediticio` VARCHAR(255) NULL,
    `fuente_ingreso` VARCHAR(255) NULL,
    `estado_cobranza_actual` VARCHAR(255) NULL,
    `contactabilidad_interna` VARCHAR(100) NULL,
    `fecha_otorgamiento_credito` DATE NULL,
    `actividad_laboral` VARCHAR(255) NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_cartera_wandoo_detalle_operacion` (`operacion_id`),
    KEY `idx_cartera_wandoo_detalle_documento` (`documento_cliente`),
    KEY `idx_cartera_wandoo_detalle_batch` (`batch_id`),
    KEY `idx_cartera_wandoo_detalle_source` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
