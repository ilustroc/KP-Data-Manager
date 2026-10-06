-- KP Data Manager - Carteras 1 / direcciones Silver normalizadas
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.
-- No agrega foreign keys cross-schema; la trazabilidad queda indexada.

CREATE TABLE `kp_silver`.`cartera_direcciones` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `entidad` VARCHAR(50) NOT NULL,
    `tipo_direccion` VARCHAR(50) NOT NULL,
    `direccion` VARCHAR(500) NULL,
    `referencia` VARCHAR(500) NULL,
    `referencia1` VARCHAR(500) NULL,
    `referencia2` VARCHAR(500) NULL,
    `ubicacion` VARCHAR(500) NULL,
    `codigo_postal` VARCHAR(100) NULL,
    `ubigeo` VARCHAR(100) NULL,
    `departamento` VARCHAR(100) NULL,
    `provincia` VARCHAR(100) NULL,
    `distrito` VARCHAR(100) NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_cartera_direcciones_operacion` (`operacion_id`),
    KEY `idx_cartera_direcciones_entidad_documento` (`entidad`, `documento_cliente`),
    KEY `idx_cartera_direcciones_ubigeo` (`ubigeo`),
    KEY `idx_cartera_direcciones_departamento` (`departamento`),
    KEY `idx_cartera_direcciones_batch` (`batch_id`),
    KEY `idx_cartera_direcciones_source` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
