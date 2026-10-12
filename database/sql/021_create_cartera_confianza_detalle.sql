-- KP Data Manager - detalle Silver Financiera Confianza v1
-- MySQL 5.7.33 compatible. Revisión y ejecución manual obligatorias.
-- No define UNIQUE de negocio ni claves foráneas entre esquemas.

CREATE TABLE `kp_silver`.`cartera_confianza_detalle` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `saldo_capital_mo` DECIMAL(15,2) NULL,
    `saldo_capital_mn` DECIMAL(15,2) NULL,
    `interes_vencido` DECIMAL(15,2) NULL,
    `interes_compensatorio` DECIMAL(15,2) NULL,
    `interes_moratorio` DECIMAL(15,2) NULL,
    `seguros` DECIMAL(15,2) NULL,
    `comisiones` DECIMAL(15,2) NULL,
    `gastos_judiciales` DECIMAL(15,2) NULL,
    `moneda_origen` VARCHAR(50) NULL,
    `codigo_sucursal_credito` VARCHAR(100) NULL,
    `nombre_sucursal_credito` VARCHAR(255) NULL,
    `corredor` VARCHAR(255) NULL,
    `nombre_modulo_origen` VARCHAR(255) NULL,
    `estado_operacion` VARCHAR(255) NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_cartera_confianza_detalle_operacion` (`operacion_id`),
    KEY `idx_cartera_confianza_detalle_documento` (`documento_cliente`),
    KEY `idx_cartera_confianza_detalle_batch` (`batch_id`),
    KEY `idx_cartera_confianza_detalle_source` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
