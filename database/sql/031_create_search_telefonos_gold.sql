-- KP Data Manager - DM-F3 / contrato Gold TELEFONOS v1
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- Estado actual por documento/teléfono; una sola fuente TELEFONOS autorizada en DM-F3.

CREATE TABLE `kp_gold`.`search_telefonos` (
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `telefono` CHAR(9) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `operador` VARCHAR(32) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    `fecha_data` DATE NOT NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`documento`, `telefono`),
    KEY `idx_search_telefonos_document_date` (`documento`, `fecha_data`),
    KEY `idx_search_telefonos_source_batch` (`source_code`, `batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
