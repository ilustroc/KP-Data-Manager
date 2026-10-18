-- KP Data Manager - DM-F2 / contrato Gold PERSONAS v1
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- Una fila operativa por documento; una sola fuente PERSONAS autorizada en DM-F2.

CREATE TABLE `kp_gold`.`search_person_index` (
    `documento` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `tipo_documento` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `nombre_completo` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL,
    `paterno` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `materno` VARCHAR(150) COLLATE utf8mb4_unicode_ci NULL,
    `nombres` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `fecha_nacimiento` DATE NULL,
    `sexo` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL,
    `estado_civil` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `direccion_origen` TEXT COLLATE utf8mb4_unicode_ci NULL,
    `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`documento`),
    KEY `idx_search_person_index_source_batch` (`source_code`, `batch_id`),
    KEY `idx_search_person_index_updated` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
