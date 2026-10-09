-- KP Data Manager - detalle Silver Compartamos v1
-- MySQL 5.7.33 compatible. Revisión y ejecución manual obligatorias.
-- No define UNIQUE de negocio ni claves foráneas entre esquemas.

CREATE TABLE `kp_silver`.`cartera_compartamos_detalle` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `documento_fuente` VARCHAR(100) NULL,
    `tipo_cambio` DECIMAL(18,6) NULL,
    `saldo_capital_soles` DECIMAL(15,2) NULL,
    `lote` VARCHAR(100) NULL,
    `empresa` VARCHAR(255) NULL,
    `anio_desembolso` SMALLINT UNSIGNED NULL,
    `fecha_nacimiento` DATE NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_cartera_compartamos_detalle_operacion` (`operacion_id`),
    KEY `idx_cartera_compartamos_detalle_documento` (`documento_cliente`),
    KEY `idx_cartera_compartamos_detalle_batch` (`batch_id`),
    KEY `idx_cartera_compartamos_detalle_source` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
