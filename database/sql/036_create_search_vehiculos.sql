-- KP Data Manager - DM-F4 / Silver histórico VEHICULOS. MySQL 5.7.33.
CREATE TABLE `kp_silver`.`search_vehiculos` (
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
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`vehicle_id`),
    UNIQUE KEY `uq_search_vehiculos_batch_record` (`batch_id`, `record_hash`),
    KEY `idx_search_vehiculos_document_batch` (`documento`, `batch_id`),
    KEY `idx_search_vehiculos_document_plate` (`documento`, `placa`),
    KEY `idx_search_vehiculos_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_vehiculos_source_raw` (`source_raw_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
