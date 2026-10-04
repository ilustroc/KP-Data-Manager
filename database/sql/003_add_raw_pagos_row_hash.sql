-- KP Data Manager
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.
-- No crea un índice UNIQUE hasta analizar y completar el histórico.

ALTER TABLE `kp_bronze`.`raw_pagos`
    ADD COLUMN `row_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL AFTER `ingested_at`,
    ADD KEY `idx_raw_pagos_row_hash` (`row_hash`);
