-- KP Data Manager - garantías Silver comunes
-- Compatible con MySQL 5.7.33. Pendiente de revisión y ejecución manual.

CREATE TABLE `kp_silver`.`cartera_garantias` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `entidad` VARCHAR(50) NOT NULL,
    `orden` TINYINT UNSIGNED NOT NULL,
    `tipo_garantia` VARCHAR(255) NULL,
    `monto` DECIMAL(15,2) NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_cartera_garantias_operacion` (`operacion_id`),
    KEY `idx_cartera_garantias_entidad_documento` (`entidad`, `documento_cliente`),
    KEY `idx_cartera_garantias_tipo` (`tipo_garantia`),
    KEY `idx_cartera_garantias_batch` (`batch_id`),
    KEY `idx_cartera_garantias_source` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
