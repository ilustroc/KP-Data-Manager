-- KP Data Manager
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.
-- Precondición verificada en el snapshot: los batch_id históricos actuales son NULL.
-- No agrega foreign key entre esquemas; conserva solamente trazabilidad indexada.

ALTER TABLE `kp_bronze`.`raw_pagos`
    MODIFY COLUMN `batch_id` BIGINT UNSIGNED NULL AFTER `source_file`,
    ADD KEY `idx_raw_pagos_batch_id` (`batch_id`);
