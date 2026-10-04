-- KP Data Manager
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.

CREATE TABLE `kp_control`.`import_error` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `numero_fila` BIGINT UNSIGNED NOT NULL,
    `campo` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `valor` TEXT COLLATE utf8mb4_unicode_ci,
    `error` VARCHAR(500) COLLATE utf8mb4_unicode_ci NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_import_error_batch_row` (`batch_id`, `numero_fila`),
    KEY `idx_import_error_numero_fila` (`numero_fila`),
    CONSTRAINT `fk_import_error_batch`
        FOREIGN KEY (`batch_id`)
        REFERENCES `kp_control`.`import_batch` (`batch_id`)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
