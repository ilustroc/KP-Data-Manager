-- SBS DETALLE: índice para la verificación bidireccional Silver <-> Scope.
-- Ejecutar manualmente tras una revisión de EXPLAIN; no es una migración automática.
-- Compatible con InnoDB MySQL 5.7.33 y MySQL 8.0.
-- ALGORITHM=INPLACE y LOCK=NONE hacen que la operación falle, en vez de bloquear,
-- si el servidor no puede crear el índice en línea.

SET @kpdm_sbs_detail_index_exists := (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = 'kp_silver'
      AND table_name = 'search_sbs_detalle'
      AND index_name = 'idx_sbs_detail_batch_document'
);

SET @kpdm_sbs_detail_index_sql := IF(
    @kpdm_sbs_detail_index_exists = 0,
    'ALTER TABLE `kp_silver`.`search_sbs_detalle` ADD KEY `idx_sbs_detail_batch_document` (`batch_id`, `documento`), ALGORITHM=INPLACE, LOCK=NONE',
    'SELECT ''idx_sbs_detail_batch_document already exists'' AS status'
);

PREPARE kpdm_sbs_detail_index_statement FROM @kpdm_sbs_detail_index_sql;
EXECUTE kpdm_sbs_detail_index_statement;
DEALLOCATE PREPARE kpdm_sbs_detail_index_statement;

SHOW INDEX FROM `kp_silver`.`search_sbs_detalle`
WHERE Key_name = 'idx_sbs_detail_batch_document';
