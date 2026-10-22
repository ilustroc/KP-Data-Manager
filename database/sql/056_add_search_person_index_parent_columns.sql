-- PERSONAS Gold: incorpora padre y madre en instalaciones existentes.
-- Ejecutar manualmente, después de respaldo y fuera de una publicación SEARCH.
-- Compatible con InnoDB MySQL 5.7.33 y MySQL 8.0. No forma parte de un despliegue automático.
--
-- El contrato físico es VARCHAR(500) NULL CHARACTER SET utf8mb4 COLLATE
-- utf8mb4_unicode_ci. Si una columna existente no coincide, el script aborta con
-- MYSQL_ERRNO 30010 antes de ejecutar DDL, en lugar de modificar su definición.
--
-- MySQL 8.0.29+ puede agregar columnas en cualquier posición con INSTANT. Para
-- 5.7 y 8.0 anteriores se usa INPLACE, LOCK=NONE. Si INSTANT no es compatible
-- con las propiedades de la tabla, se reintenta INPLACE, LOCK=NONE; ambos modos
-- fallan en vez de degradar a COPY o a un lock más restrictivo.

DROP PROCEDURE IF EXISTS `kp_gold`.`kpdm_add_search_person_index_parent_columns`;

DELIMITER //

CREATE PROCEDURE `kp_gold`.`kpdm_add_search_person_index_parent_columns`()
BEGIN
    DECLARE parent_columns_existing INT UNSIGNED DEFAULT 0;
    DECLARE parent_columns_invalid INT UNSIGNED DEFAULT 0;
    DECLARE padre_exists INT UNSIGNED DEFAULT 0;
    DECLARE madre_exists INT UNSIGNED DEFAULT 0;
    DECLARE mysql_major INT UNSIGNED DEFAULT 0;
    DECLARE mysql_minor INT UNSIGNED DEFAULT 0;
    DECLARE mysql_patch INT UNSIGNED DEFAULT 0;
    DECLARE add_clauses TEXT;
    DECLARE ddl_algorithm VARCHAR(32) DEFAULT 'NOT_REQUIRED';
    DECLARE instant_failed BOOLEAN DEFAULT FALSE;

    SELECT COUNT(*)
    INTO parent_columns_existing
    FROM information_schema.columns
    WHERE table_schema = 'kp_gold'
      AND table_name = 'search_person_index'
      AND column_name IN ('padre', 'madre');

    SELECT COUNT(*)
    INTO parent_columns_invalid
    FROM information_schema.columns
    WHERE table_schema = 'kp_gold'
      AND table_name = 'search_person_index'
      AND column_name IN ('padre', 'madre')
      AND (
          column_type <> 'varchar(500)'
          OR is_nullable <> 'YES'
          OR character_set_name <> 'utf8mb4'
          OR collation_name <> 'utf8mb4_unicode_ci'
      );

    IF parent_columns_invalid > 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MYSQL_ERRNO = 30010,
                MESSAGE_TEXT = 'Existing parent columns do not match the PERSONAS Gold contract';
    END IF;

    SELECT COUNT(*)
    INTO padre_exists
    FROM information_schema.columns
    WHERE table_schema = 'kp_gold'
      AND table_name = 'search_person_index'
      AND column_name = 'padre';

    SELECT COUNT(*)
    INTO madre_exists
    FROM information_schema.columns
    WHERE table_schema = 'kp_gold'
      AND table_name = 'search_person_index'
      AND column_name = 'madre';

    SET add_clauses = '';

    IF padre_exists = 0 THEN
        SET add_clauses =
            'ADD COLUMN `padre` VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL AFTER `direccion_origen`';
    END IF;

    IF madre_exists = 0 THEN
        SET add_clauses = CONCAT(
            add_clauses,
            IF(add_clauses = '', '', ', '),
            'ADD COLUMN `madre` VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL AFTER `padre`'
        );
    END IF;

    IF add_clauses <> '' THEN
        SET mysql_major = CAST(SUBSTRING_INDEX(VERSION(), '.', 1) AS UNSIGNED);
        SET mysql_minor = CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(VERSION(), '.', 2), '.', -1) AS UNSIGNED);
        SET mysql_patch = CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(SUBSTRING_INDEX(VERSION(), '.', 3), '.', -1), '-', 1) AS UNSIGNED);

        IF mysql_major > 8
           OR (mysql_major = 8 AND (mysql_minor > 0 OR (mysql_minor = 0 AND mysql_patch >= 29))) THEN
            BEGIN
                DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET instant_failed = TRUE;

                SET @kpdm_gold_parent_ddl = CONCAT(
                    'ALTER TABLE `kp_gold`.`search_person_index` ',
                    add_clauses,
                    ', ALGORITHM=INSTANT'
                );
                PREPARE kpdm_gold_parent_ddl_statement FROM @kpdm_gold_parent_ddl;
                EXECUTE kpdm_gold_parent_ddl_statement;
                DEALLOCATE PREPARE kpdm_gold_parent_ddl_statement;
            END;

            IF instant_failed THEN
                SET ddl_algorithm = 'INPLACE_FALLBACK';
                SET @kpdm_gold_parent_ddl = CONCAT(
                    'ALTER TABLE `kp_gold`.`search_person_index` ',
                    add_clauses,
                    ', ALGORITHM=INPLACE, LOCK=NONE'
                );
                PREPARE kpdm_gold_parent_ddl_statement FROM @kpdm_gold_parent_ddl;
                EXECUTE kpdm_gold_parent_ddl_statement;
                DEALLOCATE PREPARE kpdm_gold_parent_ddl_statement;
            ELSE
                SET ddl_algorithm = 'INSTANT';
            END IF;
        ELSE
            SET ddl_algorithm = 'INPLACE';
            SET @kpdm_gold_parent_ddl = CONCAT(
                'ALTER TABLE `kp_gold`.`search_person_index` ',
                add_clauses,
                ', ALGORITHM=INPLACE, LOCK=NONE'
            );
            PREPARE kpdm_gold_parent_ddl_statement FROM @kpdm_gold_parent_ddl;
            EXECUTE kpdm_gold_parent_ddl_statement;
            DEALLOCATE PREPARE kpdm_gold_parent_ddl_statement;
        END IF;
    END IF;

    SELECT
        ddl_algorithm AS `ddl_algorithm`,
        parent_columns_existing AS `parent_columns_existing_before_change`;
END//

DELIMITER ;

CALL `kp_gold`.`kpdm_add_search_person_index_parent_columns`();
DROP PROCEDURE `kp_gold`.`kpdm_add_search_person_index_parent_columns`;

SHOW COLUMNS FROM `kp_gold`.`search_person_index` WHERE Field IN ('padre', 'madre');
