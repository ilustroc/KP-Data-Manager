-- KP Data Manager - DM-F3 / Silver histórico TELEFONOS
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- Reutiliza Bronze SEARCH genérico y no modifica PERSONAS, PAGOS ni CARTERA.

CREATE TABLE `kp_silver`.`search_telefonos` (
    `phone_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `telefono` CHAR(9) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `operador` VARCHAR(32) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    `operador_raw` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `fecha_data` DATE NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`phone_id`),
    UNIQUE KEY `uq_search_telefonos_batch_document_phone`
        (`batch_id`, `documento`, `telefono`),
    KEY `idx_search_telefonos_document_batch` (`documento`, `batch_id`),
    KEY `idx_search_telefonos_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_telefonos_phone_document` (`telefono`, `documento`),
    KEY `idx_search_telefonos_source_raw` (`source_raw_id`),
    KEY `idx_search_telefonos_record_hash` (`record_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
