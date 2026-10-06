-- KP Data Manager - Carteras 1
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.

ALTER TABLE `kp_control`.`import_batch`
    ADD COLUMN `entidad` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL AFTER `tipo`,
    ADD COLUMN `perfil_version` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_general_ci NULL AFTER `entidad`,
    ADD KEY `idx_import_batch_tipo_entidad_perfil` (`tipo`, `entidad`, `perfil_version`),
    ADD KEY `idx_import_batch_entidad` (`entidad`);
