-- PERSONAS Gold: backfill histórico de padre y madre.
-- Ejecutar solamente después de 056. El advisory lock coincide con la publicación
-- PERSONAS / BASE_PERSONAS y evita competir con ese flujo mientras está activo.
-- El script preserva updated_at: el valor representa la publicación Gold original.
-- Si alguna fila Gold no tiene el mismo documento, batch_id y source_code en Silver,
-- no actualiza ninguna fila y reporta la cantidad para investigación.

START TRANSACTION;

SELECT GET_LOCK('kpdm:search:211b99d4f10049ef0aef57e46bf9fb957b7d8ab3', 0)
INTO @kpdm_personas_parent_lock_acquired;

SET @kpdm_personas_parent_unmatched := (
    SELECT COUNT(*)
    FROM `kp_gold`.`search_person_index` AS gold
    LEFT JOIN `kp_silver`.`search_personas` AS silver
        ON silver.documento = gold.documento
       AND silver.batch_id = gold.batch_id
       AND silver.source_code = gold.source_code
    WHERE silver.person_id IS NULL
);

SELECT @kpdm_personas_parent_unmatched AS `gold_without_exact_silver_lineage`;

SET @kpdm_personas_parent_backfill_sql := IF(
    @kpdm_personas_parent_lock_acquired = 1
    AND @kpdm_personas_parent_unmatched = 0,
    'UPDATE `kp_gold`.`search_person_index` AS gold INNER JOIN `kp_silver`.`search_personas` AS silver ON silver.documento = gold.documento AND silver.batch_id = gold.batch_id AND silver.source_code = gold.source_code SET gold.padre = silver.padre, gold.madre = silver.madre WHERE NOT (gold.padre <=> silver.padre) OR NOT (gold.madre <=> silver.madre)',
    'SELECT ''backfill aborted: publication lock unavailable or Gold rows without exact Silver lineage'' AS status'
);

PREPARE kpdm_personas_parent_backfill_statement FROM @kpdm_personas_parent_backfill_sql;
EXECUTE kpdm_personas_parent_backfill_statement;
SET @kpdm_personas_parent_rows_updated := ROW_COUNT();
DEALLOCATE PREPARE kpdm_personas_parent_backfill_statement;

SELECT
    @kpdm_personas_parent_lock_acquired AS `publication_lock_acquired`,
    @kpdm_personas_parent_unmatched AS `gold_without_exact_silver_lineage`,
    IF(
        @kpdm_personas_parent_lock_acquired = 1
        AND @kpdm_personas_parent_unmatched = 0,
        @kpdm_personas_parent_rows_updated,
        NULL
    ) AS `rows_updated`;

COMMIT;

SELECT RELEASE_LOCK('kpdm:search:211b99d4f10049ef0aef57e46bf9fb957b7d8ab3')
AS `publication_lock_released`;

-- Rollback operativo de datos: restaurar únicamente desde un respaldo tomado antes del backfill.
-- No se debe reconstruir padre/madre eligiendo valores de batches Silver distintos.
