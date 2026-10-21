-- ESSALUD: índice para la verificación bidireccional Silver <-> Scope.
-- Ejecutar manualmente tras una revisión de EXPLAIN; no es una migración automática.
-- Compatible con InnoDB MySQL 5.7.33 y MySQL 8.0.
-- ALGORITHM=INPLACE y LOCK=NONE hacen que la operación falle, en vez de bloquear,
-- si el servidor no puede crear el índice en línea.

SET @kpdm_essalud_index_exists := (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = 'kp_silver'
      AND table_name = 'search_laboral_essalud'
      AND index_name = 'idx_essalud_batch_document'
);

SET @kpdm_essalud_index_sql := IF(
    @kpdm_essalud_index_exists = 0,
    'ALTER TABLE `kp_silver`.`search_laboral_essalud` ADD KEY `idx_essalud_batch_document` (`batch_id`, `documento`), ALGORITHM=INPLACE, LOCK=NONE',
    'SELECT ''idx_essalud_batch_document already exists'' AS status'
);

PREPARE kpdm_essalud_index_statement FROM @kpdm_essalud_index_sql;
EXECUTE kpdm_essalud_index_statement;
DEALLOCATE PREPARE kpdm_essalud_index_statement;

SHOW INDEX FROM `kp_silver`.`search_laboral_essalud`
WHERE Key_name = 'idx_essalud_batch_document';
