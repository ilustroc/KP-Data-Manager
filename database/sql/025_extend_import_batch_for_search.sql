-- KP Data Manager - DM-F1 / evolución compatible de import_batch para SEARCH
-- Compatible con MySQL 5.7.33. Revisión y ejecución manual obligatorias.
-- Todas las columnas son NULL para conservar batches históricos PAGOS/CARTERA.
-- La idempotencia SEARCH no hace UNIQUE solamente sobre archivo_sha256.

ALTER TABLE `kp_control`.`import_batch`
    ADD COLUMN `dataset_code` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NULL AFTER `perfil_version`,
    ADD COLUMN `source_code` VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL AFTER `dataset_code`,
    ADD COLUMN `refresh_mode` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NULL AFTER `source_code`,
    ADD COLUMN `rows_valid` BIGINT UNSIGNED NULL AFTER `filas_error`,
    ADD COLUMN `rows_invalid` BIGINT UNSIGNED NULL AFTER `rows_valid`,
    ADD COLUMN `rows_published` BIGINT UNSIGNED NULL AFTER `rows_invalid`,
    ADD COLUMN `scope_count` BIGINT UNSIGNED NULL AFTER `rows_published`,
    ADD COLUMN `received_at` DATETIME NULL AFTER `scope_count`,
    ADD COLUMN `validated_at` DATETIME NULL AFTER `received_at`,
    ADD COLUMN `published_at` DATETIME NULL AFTER `validated_at`,
    ADD COLUMN `uploaded_by_user_id` BIGINT UNSIGNED NULL AFTER `published_at`,
    ADD COLUMN `mapping_version` INT UNSIGNED NULL AFTER `uploaded_by_user_id`,
    ADD COLUMN `idempotency_key` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL AFTER `mapping_version`,
    ADD UNIQUE KEY `uq_import_batch_idempotency_key` (`idempotency_key`),
    ADD KEY `idx_import_batch_search_context` (`dataset_code`, `source_code`, `refresh_mode`, `batch_id`),
    ADD KEY `idx_import_batch_uploaded_by` (`uploaded_by_user_id`);
