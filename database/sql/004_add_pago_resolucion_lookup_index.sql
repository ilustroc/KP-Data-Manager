-- KP Data Manager
-- Compatible con MySQL 5.7.33.
-- Pendiente de revisión y ejecución manual. No fue aplicado a producción.

ALTER TABLE `kp_control`.`pago_documento_resolucion`
    ADD KEY `idx_pago_resolucion_raw_activo` (`raw_pago_id`, `activo`);

-- `idx_raw_pago_id` queda temporalmente para que su eliminación se decida
-- después de revisar EXPLAIN y el costo de escritura en producción.
