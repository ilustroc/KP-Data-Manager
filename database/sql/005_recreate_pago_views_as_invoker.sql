-- KP Data Manager
-- Compatible con MySQL 5.7.33.
-- Definición versionada de las vistas vigentes. No ejecutar automáticamente.
-- Requiere que el usuario de aplicación tenga SELECT explícito sobre los
-- objetos subyacentes de kp_bronze y kp_control.

CREATE OR REPLACE ALGORITHM=UNDEFINED
SQL SECURITY INVOKER
VIEW `kp_silver`.`v_pagos_actuales` AS
SELECT
    `P`.`raw_id` AS `raw_id`,
    `P`.`FECHA` AS `FECHA`,
    `P`.`DOCUMENTO` AS `DOCUMENTO_ORIGINAL`,
    (
        CASE
            WHEN ISNULL(NULLIF(TRIM(COALESCE(`R`.`documento_nuevo`, `P`.`DOCUMENTO`)), '')) THEN NULL
            WHEN (
                (TRIM(COALESCE(`R`.`documento_nuevo`, `P`.`DOCUMENTO`)) REGEXP '^[0-9]+$')
                AND (CHAR_LENGTH(TRIM(COALESCE(`R`.`documento_nuevo`, `P`.`DOCUMENTO`))) < 8)
            ) THEN LPAD(TRIM(COALESCE(`R`.`documento_nuevo`, `P`.`DOCUMENTO`)), 8, '0')
            ELSE TRIM(COALESCE(`R`.`documento_nuevo`, `P`.`DOCUMENTO`))
        END
    ) AS `DOCUMENTO`,
    `P`.`MONTO` AS `MONTO`,
    `P`.`ACUMULADO` AS `ACUMULADO`,
    `P`.`RECAUDO` AS `RECAUDO`,
    `P`.`OPERACION` AS `OPERACION`,
    `P`.`COMENTARIO` AS `COMENTARIO`,
    `P`.`HORA` AS `HORA`,
    `P`.`source_file` AS `source_file`,
    `P`.`batch_id` AS `batch_id`,
    `P`.`ingested_at` AS `ingested_at`
FROM `kp_bronze`.`raw_pagos` AS `P`
LEFT JOIN `kp_control`.`pago_documento_resolucion` AS `R`
    ON `R`.`raw_pago_id` = `P`.`raw_id`
    AND `R`.`activo` = 1;

CREATE OR REPLACE ALGORITHM=UNDEFINED
SQL SECURITY INVOKER
VIEW `kp_silver`.`v_pagos_sin_identificar` AS
SELECT
    `raw_id`,
    `FECHA`,
    `DOCUMENTO_ORIGINAL`,
    `DOCUMENTO`,
    `MONTO`,
    `ACUMULADO`,
    `RECAUDO`,
    `OPERACION`,
    `COMENTARIO`,
    `HORA`,
    `source_file`,
    `batch_id`,
    `ingested_at`
FROM `kp_silver`.`v_pagos_actuales`
WHERE `DOCUMENTO` IS NULL
    OR TRIM(`DOCUMENTO`) = '';
