-- KP Data Manager - habilitación controlada de UPSERT para TELEFONOS / BASE_TELEFONOS.
-- Compatible con MySQL 5.7.33. Ejecutar manualmente solo después de aprobar las pruebas.
-- No forma parte de un despliegue automático.

START TRANSACTION;

SELECT `dataset_code`, `source_code`, `is_active`, `allows_upsert`
FROM `kp_control`.`import_dataset_source`
WHERE `dataset_code` = 'TELEFONOS'
  AND `source_code` = 'BASE_TELEFONOS'
FOR UPDATE;

UPDATE `kp_control`.`import_dataset_source`
SET `allows_upsert` = 1,
    `updated_at` = UTC_TIMESTAMP()
WHERE `dataset_code` = 'TELEFONOS'
  AND `source_code` = 'BASE_TELEFONOS'
  AND `is_active` = 1;

SELECT ROW_COUNT() AS `filas_modificadas`;

SELECT `dataset_code`, `source_code`, `allows_upsert`
FROM `kp_control`.`import_dataset_source`
WHERE `allows_upsert` = 1
ORDER BY `dataset_code`, `source_code`;

COMMIT;

-- Rollback operativo, si fuera aprobado posteriormente:
-- UPDATE `kp_control`.`import_dataset_source`
-- SET `allows_upsert` = 0, `updated_at` = UTC_TIMESTAMP()
-- WHERE `dataset_code` = 'TELEFONOS' AND `source_code` = 'BASE_TELEFONOS';
