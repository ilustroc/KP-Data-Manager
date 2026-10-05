-- KP Data Manager
-- Corrección manual y controlada de fechas históricas almacenadas como hora local.
-- Compatible con MySQL 5.7.33. NO ejecutar sin identificar primero la resolución.
--
-- La variable queda en NULL deliberadamente para que una ejecución accidental
-- no modifique filas. Asignar el id_resolucion validado antes de usar el script.

SET @target_resolution_id = NULL;
SET @expected_local_datetime = '2026-10-04 22:33:58';
SET @corrected_utc_datetime = '2026-10-05 03:33:58';

START TRANSACTION;

SELECT
    `id_resolucion`,
    `raw_pago_id`,
    `fecha_modificacion`,
    `usuario`,
    `motivo`
FROM `kp_control`.`pago_documento_resolucion`
WHERE `id_resolucion` = @target_resolution_id
FOR UPDATE;

UPDATE `kp_control`.`pago_documento_resolucion`
SET `fecha_modificacion` = @corrected_utc_datetime
WHERE `id_resolucion` = @target_resolution_id
    AND `fecha_modificacion` = @expected_local_datetime;

SELECT ROW_COUNT() AS `filas_corregidas`;

SELECT
    `id_resolucion`,
    `raw_pago_id`,
    `fecha_modificacion`
FROM `kp_control`.`pago_documento_resolucion`
WHERE `id_resolucion` = @target_resolution_id;

-- Mantener ROLLBACK durante la revisión. Sustituirlo manualmente por COMMIT
-- únicamente después de confirmar id_resolucion, fecha original y fecha UTC.
ROLLBACK;
