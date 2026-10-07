-- KP Data Manager - avales Silver comunes
-- Compatible con MySQL 5.7.33. Pendiente de revisión y ejecución manual.

CREATE TABLE `kp_silver`.`cartera_avales` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `entidad` VARCHAR(50) NOT NULL,
    `orden` TINYINT UNSIGNED NOT NULL,
    `nombre_aval` VARCHAR(255) NULL,
    `tipo_documento` VARCHAR(100) NULL,
    `documento_aval` VARCHAR(100) NULL,
    `telefono` VARCHAR(500) NULL,
    `direccion` VARCHAR(1000) NULL,
    `referencia` VARCHAR(1000) NULL,
    `distrito` VARCHAR(255) NULL,
    `cantidad_reportada` INT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_cartera_avales_operacion` (`operacion_id`),
    KEY `idx_cartera_avales_entidad_documento` (`entidad`, `documento_cliente`),
    KEY `idx_cartera_avales_documento_aval` (`documento_aval`),
    KEY `idx_cartera_avales_batch` (`batch_id`),
    KEY `idx_cartera_avales_source` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
