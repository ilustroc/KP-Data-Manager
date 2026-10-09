-- KP Data Manager - auditoría de eliminación de cargas históricas
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- No define FK a import_batch porque el registro original se elimina.

CREATE TABLE `kp_control`.`import_deletion_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `batch_id_original` BIGINT UNSIGNED NOT NULL,
    `tipo` VARCHAR(50) NOT NULL,
    `entidad` VARCHAR(50) NULL,
    `origen` VARCHAR(50) NULL,
    `archivo_original` VARCHAR(255) NULL,
    `archivo_interno` VARCHAR(255) NULL,
    `file_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `filas_archivo` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `filas_insertadas` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `filas_error` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `deleted_by_user_id` BIGINT UNSIGNED NOT NULL,
    `deleted_by_name` VARCHAR(255) NOT NULL,
    `deleted_at` DATETIME NOT NULL,
    `file_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    `warning` VARCHAR(500) NULL,
    PRIMARY KEY (`id`),
    KEY `idx_import_deletion_batch` (`batch_id_original`),
    KEY `idx_import_deletion_entity` (`entidad`),
    KEY `idx_import_deletion_user` (`deleted_by_user_id`),
    KEY `idx_import_deletion_date` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
