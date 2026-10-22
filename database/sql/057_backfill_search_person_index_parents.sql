-- PERSONAS Gold: backfill histórico de padre y madre.
-- Ejecutar solamente después de 056. El advisory lock coincide con la publicación
-- PERSONAS / BASE_PERSONAS y evita competir con ese flujo mientras está activo.
-- El script preserva updated_at: el valor representa la publicación Gold original.
-- Si alguna fila Gold no tiene el mismo documento, batch_id y source_code en Silver,
-- aborta con MYSQL_ERRNO 30003 antes de actualizar filas.
--
-- El EXIT HANDLER revierte la transacción y libera el advisory lock también en
-- errores SQL. Los advisory locks no se liberan por COMMIT ni ROLLBACK, por lo que
-- la liberación explícita es obligatoria.

DROP PROCEDURE IF EXISTS `kp_gold`.`kpdm_backfill_search_person_index_parents`;

DELIMITER //

CREATE PROCEDURE `kp_gold`.`kpdm_backfill_search_person_index_parents`()
main: BEGIN
    DECLARE lock_acquired TINYINT DEFAULT 0;
    DECLARE lock_released TINYINT DEFAULT NULL;
    DECLARE unmatched_rows BIGINT UNSIGNED DEFAULT 0;
    DECLARE rows_updated BIGINT UNSIGNED DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;

        IF lock_acquired = 1 THEN
            DO RELEASE_LOCK('kpdm:search:211b99d4f10049ef0aef57e46bf9fb957b7d8ab3');
        END IF;

        RESIGNAL;
    END;

    SELECT GET_LOCK('kpdm:search:211b99d4f10049ef0aef57e46bf9fb957b7d8ab3', 0)
    INTO lock_acquired;

    IF lock_acquired IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MYSQL_ERRNO = 30001,
                MESSAGE_TEXT = 'Unable to evaluate PERSONAS publication lock';
    END IF;

    IF lock_acquired <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MYSQL_ERRNO = 30002,
                MESSAGE_TEXT = 'PERSONAS publication lock is unavailable';
    END IF;

    START TRANSACTION;

    SELECT COUNT(*)
    INTO unmatched_rows
    FROM `kp_gold`.`search_person_index` AS gold
    LEFT JOIN `kp_silver`.`search_personas` AS silver
        ON silver.documento = gold.documento
       AND silver.batch_id = gold.batch_id
       AND silver.source_code = gold.source_code
    WHERE silver.person_id IS NULL;

    IF unmatched_rows > 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MYSQL_ERRNO = 30003,
                MESSAGE_TEXT = 'PERSONAS Gold rows are missing exact Silver lineage';
    END IF;

    UPDATE `kp_gold`.`search_person_index` AS gold
    INNER JOIN `kp_silver`.`search_personas` AS silver
        ON silver.documento = gold.documento
       AND silver.batch_id = gold.batch_id
       AND silver.source_code = gold.source_code
    SET gold.padre = silver.padre,
        gold.madre = silver.madre
    WHERE NOT (gold.padre <=> silver.padre)
       OR NOT (gold.madre <=> silver.madre);

    SET rows_updated = ROW_COUNT();

    COMMIT;

    SELECT RELEASE_LOCK('kpdm:search:211b99d4f10049ef0aef57e46bf9fb957b7d8ab3')
    INTO lock_released;
    SET lock_acquired = 0;

    IF lock_released <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MYSQL_ERRNO = 30004,
                MESSAGE_TEXT = 'PERSONAS publication lock could not be released';
    END IF;

    SELECT
        1 AS `publication_lock_acquired`,
        1 AS `publication_lock_released`,
        unmatched_rows AS `gold_without_exact_silver_lineage`,
        rows_updated AS `rows_updated`;
END//

DELIMITER ;

CALL `kp_gold`.`kpdm_backfill_search_person_index_parents`();
DROP PROCEDURE `kp_gold`.`kpdm_backfill_search_person_index_parents`;

-- Rollback operativo de datos: restaurar únicamente desde un respaldo tomado antes del backfill.
-- No se debe reconstruir padre/madre eligiendo valores de batches Silver distintos.
