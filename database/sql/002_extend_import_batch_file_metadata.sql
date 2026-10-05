-- KP Data Manager
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.
-- Las columnas son NULL para permitir una ampliación segura con filas históricas.

ALTER TABLE `kp_control`.`import_batch`
    ADD COLUMN `archivo_original` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL AFTER `archivo`,
    ADD COLUMN `archivo_interno` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL AFTER `archivo_original`,
    ADD COLUMN `archivo_ruta` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL AFTER `archivo_interno`,
    ADD COLUMN `archivo_extension` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_general_ci NULL AFTER `archivo_ruta`,
    ADD COLUMN `archivo_mime` VARCHAR(150) CHARACTER SET ascii COLLATE ascii_general_ci NULL AFTER `archivo_extension`,
    ADD COLUMN `archivo_tamano` BIGINT UNSIGNED NULL AFTER `archivo_mime`,
    ADD COLUMN `archivo_sha256` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL AFTER `archivo_tamano`,
    ADD KEY `idx_import_batch_origen` (`origen`),
    ADD KEY `idx_import_batch_usuario` (`usuario`),
    ADD KEY `idx_import_batch_archivo_sha256` (`archivo_sha256`);
