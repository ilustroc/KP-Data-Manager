-- KP Data Manager - DM-F2 / Silver histórico PERSONAS
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- No modifica Bronze histórico ni los flujos PAGOS/CARTERA.

CREATE TABLE `kp_silver`.`search_personas` (
    `person_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `paterno` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `materno` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `nombres` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `nombre_completo` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    `fecha_nacimiento` DATE NULL,
    `direccion_origen` TEXT COLLATE utf8mb4_unicode_ci NULL,
    `sexo` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL,
    `estado_civil` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `padre` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    `madre` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `record_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`person_id`),
    UNIQUE KEY `uq_search_personas_batch_documento` (`batch_id`, `documento`),
    KEY `idx_search_personas_documento` (`documento`, `batch_id`),
    KEY `idx_search_personas_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_personas_source_raw` (`source_raw_id`),
    KEY `idx_search_personas_record_hash` (`record_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
