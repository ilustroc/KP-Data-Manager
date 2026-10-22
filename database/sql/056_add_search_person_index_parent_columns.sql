-- PERSONAS Gold: incorpora padre y madre en instalaciones existentes.
-- Ejecutar manualmente, después de respaldo y fuera de una publicación SEARCH.
-- Compatible con InnoDB MySQL 5.7.33 y MySQL 8.0. No forma parte de un despliegue automático.
-- LOCK=NONE evita continuar si el servidor no puede hacer la operación en línea;
-- aun así, ALTER TABLE requiere un metadata lock breve al inicio y al final.

SET @kpdm_gold_padre_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = 'kp_gold'
      AND table_name = 'search_person_index'
      AND column_name = 'padre'
);

SET @kpdm_gold_add_padre_sql := IF(
    @kpdm_gold_padre_exists = 0,
    'ALTER TABLE `kp_gold`.`search_person_index` ADD COLUMN `padre` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL AFTER `direccion_origen`, ALGORITHM=INPLACE, LOCK=NONE',
    'SELECT ''padre already exists'' AS status'
);

PREPARE kpdm_gold_add_padre_statement FROM @kpdm_gold_add_padre_sql;
EXECUTE kpdm_gold_add_padre_statement;
DEALLOCATE PREPARE kpdm_gold_add_padre_statement;

SET @kpdm_gold_madre_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = 'kp_gold'
      AND table_name = 'search_person_index'
      AND column_name = 'madre'
);

SET @kpdm_gold_add_madre_sql := IF(
    @kpdm_gold_madre_exists = 0,
    'ALTER TABLE `kp_gold`.`search_person_index` ADD COLUMN `madre` VARCHAR(500) COLLATE utf8mb4_unicode_ci NULL AFTER `padre`, ALGORITHM=INPLACE, LOCK=NONE',
    'SELECT ''madre already exists'' AS status'
);

PREPARE kpdm_gold_add_madre_statement FROM @kpdm_gold_add_madre_sql;
EXECUTE kpdm_gold_add_madre_statement;
DEALLOCATE PREPARE kpdm_gold_add_madre_statement;

SHOW COLUMNS FROM `kp_gold`.`search_person_index` WHERE Field IN ('padre', 'madre');
