-- KP Data Manager - DM-F4 / Gold VEHICULOS actual. MySQL 5.7.33.
CREATE TABLE `kp_gold`.`search_vehiculos` (
    `vehicle_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `nombre_completo_fuente` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    `clase` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `anio_compra` SMALLINT UNSIGNED NULL,
    `anio_fabricacion` SMALLINT UNSIGNED NULL,
    `marca` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `placa` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_general_ci NULL,
    `placa_original` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL,
    `numero_transferencias` INT UNSIGNED NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`vehicle_id`),
    UNIQUE KEY `uq_search_vehiculos_document_record` (`documento`, `record_hash`),
    KEY `idx_search_vehiculos_document_order` (`documento`, `anio_compra`, `anio_fabricacion`, `placa`),
    KEY `idx_search_vehiculos_source_batch` (`source_code`, `batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
