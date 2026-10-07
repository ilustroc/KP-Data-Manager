-- KP Data Manager - detalle Silver Caja Arequipa v1
-- Compatible con MySQL 5.7.33. Pendiente de revisión y ejecución manual.

CREATE TABLE `kp_silver`.`cartera_caja_arequipa_detalle` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `documento_cliente` VARCHAR(100) NOT NULL,
    `analista` VARCHAR(100) NULL,
    `tipo_contable` VARCHAR(100) NULL,
    `fecha_ultimo_pago` DATE NULL,
    `cuo_pag` INT NULL,
    `actividad` VARCHAR(1000) NULL,
    `nro_avales_reportado` INT NULL,
    `codigo_sbs` VARCHAR(100) NULL,
    `monto_desembolso` DECIMAL(15,2) NULL,
    `icv` DECIMAL(15,2) NULL,
    `seguros` DECIMAL(15,2) NULL,
    `penalidad` DECIMAL(15,2) NULL,
    `otros_rubros` DECIMAL(15,2) NULL,
    `calificacion_sbs` VARCHAR(100) NULL,
    `provision` DECIMAL(15,4) NULL,
    `fecha_ingreso_judicial` DATE NULL,
    `refinanciado` VARCHAR(50) NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_caja_arequipa_detalle_operacion` (`operacion_id`),
    KEY `idx_caja_arequipa_detalle_documento` (`documento_cliente`),
    KEY `idx_caja_arequipa_detalle_batch` (`batch_id`),
    KEY `idx_caja_arequipa_detalle_source` (`source_raw_id`),
    KEY `idx_caja_arequipa_detalle_codigo_sbs` (`codigo_sbs`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
