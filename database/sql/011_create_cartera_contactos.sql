-- KP Data Manager - Carteras 1 / contactos Silver normalizados
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.
-- No crea UNIQUE sobre teléfono ni foreign keys cross-schema.

CREATE TABLE `kp_silver`.`cartera_contactos` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `entidad` VARCHAR(50) NOT NULL,
    `telefono` VARCHAR(100) NOT NULL,
    `tipo` VARCHAR(50) NULL,
    `prefijo` VARCHAR(30) NULL,
    `extension` VARCHAR(30) NULL,
    `orden` TINYINT UNSIGNED NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_cartera_contactos_operacion` (`operacion_id`),
    KEY `idx_cartera_contactos_entidad_documento` (`entidad`, `documento_cliente`),
    KEY `idx_cartera_contactos_telefono` (`telefono`),
    KEY `idx_cartera_contactos_batch` (`batch_id`),
    KEY `idx_cartera_contactos_source` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
