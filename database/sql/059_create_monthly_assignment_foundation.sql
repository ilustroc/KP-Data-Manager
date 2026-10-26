-- KP Data Manager - Fase 1 / instalación estricta de asignación mensual
-- Compatible con MySQL 5.7.33 y MySQL 8.0.
-- Ejecutar únicamente después de 061_verify_monthly_assignment_installation.sql
-- con resultado apto, respaldo confirmado y una ventana de mantenimiento.
-- No es reejecutable deliberadamente: una tabla existente es un bloqueo y no
-- debe ocultarse mediante CREATE IF NOT EXISTS. MySQL confirma DDL de forma
-- implícita; ante un fallo, detenerse y usar el procedimiento de recuperación.
-- No modifica Bronze, Silver ni las tablas Gold SEARCH existentes.
--
-- La estructura separa los 20 campos empresariales de los metadatos técnicos
-- de generación y de la trazabilidad a operaciones Silver/Bronze.

CREATE TABLE `kp_control`.`cartera_cosechas` (
    `cosecha` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `entidad` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `fecha_compra` DATE NULL,
    `origen` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`cosecha`),
    KEY `idx_cartera_cosechas_entidad_origen` (`entidad`, `origen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_control`.`zonas_departamento` (
    `departamento` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `zona` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`departamento`),
    KEY `idx_zonas_departamento_zona` (`zona`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tasas aprobadas manualmente. Esta fase no consulta BCRP/SBS ni inserta
-- cotizaciones automáticamente. La política propuesta usa SBS venta publicada
-- por BCRP PD04640PD y selecciona el último valor <= fecha_corte.
CREATE TABLE `kp_control`.`tipos_cambio` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `fecha_tipo_cambio` DATE NOT NULL,
    `moneda_origen` VARCHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `moneda_destino` VARCHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `tipo_cambio` DECIMAL(18,8) NOT NULL,
    `tipo_cambio_clase` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `fuente` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_tipos_cambio_fecha_par_clase`
        (`fecha_tipo_cambio`, `moneda_origen`, `moneda_destino`, `tipo_cambio_clase`),
    KEY `idx_tipos_cambio_lookup`
        (`moneda_origen`, `moneda_destino`, `tipo_cambio_clase`, `fecha_tipo_cambio`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Solo una política explícita puede resolver una moneda ausente o no estándar.
-- '*' representa alcance de entidad; una cosecha concreta tiene prioridad.
CREATE TABLE `kp_control`.`asignacion_politicas_moneda` (
    `entidad` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cosecha_scope` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT '*',
    `moneda_confirmada` VARCHAR(10) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `evidence` VARCHAR(1000) COLLATE utf8mb4_unicode_ci NOT NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`entidad`, `cosecha_scope`),
    KEY `idx_asignacion_politicas_moneda_active` (`is_active`, `entidad`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Las equivalencias de cosecha se aprueban una por una; nunca se normaliza
-- Silver mediante sustituciones globales de espacios o guiones bajos.
CREATE TABLE `kp_control`.`asignacion_cosecha_aliases` (
    `entidad` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cosecha_origen` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `cosecha_canonica` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `evidence` VARCHAR(1000) COLLATE utf8mb4_unicode_ci NOT NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`entidad`, `cosecha_origen`),
    KEY `idx_asignacion_cosecha_aliases_canonica` (`entidad`, `cosecha_canonica`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Toda divergencia de seed se registra/revisa antes de que un operador cambie
-- un catálogo. Los seeds iniciales no hacen UPDATE sobre valores existentes.
CREATE TABLE `kp_control`.`asignacion_catalogo_cambios` (
    `change_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `catalog_type` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `record_key` VARCHAR(150) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `current_value` TEXT COLLATE utf8mb4_unicode_ci NULL,
    `proposed_value` TEXT COLLATE utf8mb4_unicode_ci NOT NULL,
    `status` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `requested_by` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `approved_by` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `approved_at` DATETIME NULL,
    `review_note` VARCHAR(1000) COLLATE utf8mb4_unicode_ci NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`change_id`),
    KEY `idx_asignacion_catalogo_cambios_pending` (`catalog_type`, `record_key`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_control`.`asignacion_periodos` (
    `periodo` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `fecha_corte` DATE NOT NULL,
    `estado` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `active_generation_id` BIGINT UNSIGNED NULL,
    `batch_personas_id` BIGINT UNSIGNED NULL,
    `batch_personas_published_at` DATETIME NULL,
    `batch_personas_refresh_mode` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `tipo_cambio_clase` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `fecha_generacion` DATETIME NULL,
    `published_at` DATETIME NULL,
    `closed_at` DATETIME NULL,
    `cantidad_clientes` BIGINT UNSIGNED NULL,
    `cantidad_operaciones` BIGINT UNSIGNED NULL,
    `total_capital` DECIMAL(18,2) NULL,
    `total_deuda` DECIMAL(18,2) NULL,
    `total_componentes_no_capital` DECIMAL(18,2) NULL,
    `generator_version` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `audit_message` TEXT COLLATE utf8mb4_unicode_ci NULL,
    `created_at` DATETIME NOT NULL,
    `updated_at` DATETIME NOT NULL,
    PRIMARY KEY (`periodo`),
    KEY `idx_asignacion_periodos_estado` (`estado`, `fecha_corte`),
    KEY `idx_asignacion_periodos_batch_personas` (`batch_personas_id`),
    KEY `idx_asignacion_periodos_active_generation` (`active_generation_id`, `periodo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- El operador registra una única selección de batch por cosecha y periodo.
-- No se infiere "el último" lote: una ambigüedad debe bloquear la generación.
CREATE TABLE `kp_control`.`asignacion_periodo_cartera_batch` (
    `periodo` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cosecha` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `entidad` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `selected_at` DATETIME NOT NULL,
    `selected_by` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `selection_reason` VARCHAR(500) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`periodo`, `cosecha`),
    KEY `idx_asignacion_cartera_batch` (`batch_id`, `cosecha`),
    KEY `idx_asignacion_cartera_periodo_entidad` (`periodo`, `entidad`),
    CONSTRAINT `fk_asignacion_periodo_cartera_periodo`
        FOREIGN KEY (`periodo`) REFERENCES `kp_control`.`asignacion_periodos` (`periodo`)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT `fk_asignacion_periodo_cartera_cosecha`
        FOREIGN KEY (`cosecha`) REFERENCES `kp_control`.`cartera_cosechas` (`cosecha`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_gold`.`asignacion_mensual_generaciones` (
    `generation_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `periodo` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `generator_version` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `batch_personas_id` BIGINT UNSIGNED NULL,
    `fecha_corte` DATE NOT NULL,
    `tipo_cambio_clase` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `started_at` DATETIME NOT NULL,
    `finished_at` DATETIME NULL,
    `estado` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `published_at` DATETIME NULL,
    `superseded_at` DATETIME NULL,
    `failure_message` TEXT COLLATE utf8mb4_unicode_ci NULL,
    `official_periodo` CHAR(6) CHARACTER SET ascii COLLATE ascii_bin
        AS (CASE WHEN `estado` = 'PUBLISHED' THEN `periodo` ELSE NULL END) STORED,
    `rows_generated` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `operations_selected` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `anomaly_count` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`generation_id`),
    UNIQUE KEY `uq_asignacion_generacion_official_periodo` (`official_periodo`),
    UNIQUE KEY `uq_asignacion_generacion_id_periodo` (`generation_id`, `periodo`),
    KEY `idx_asignacion_generacion_periodo` (`periodo`, `estado`, `generation_id`),
    CONSTRAINT `fk_asignacion_generacion_periodo`
        FOREIGN KEY (`periodo`) REFERENCES `kp_control`.`asignacion_periodos` (`periodo`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Los veinte campos siguientes son el contrato empresarial definitivo. Los
-- únicos campos adicionales son identificadores técnicos de la fotografía.
CREATE TABLE `kp_gold`.`asignacion_mensual_clientes` (
    `assignment_client_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `generation_id` BIGINT UNSIGNED NOT NULL,
    `cadena` VARCHAR(200) COLLATE utf8mb4_unicode_ci NOT NULL,
    `fecha_compra` DATE NULL,
    `documento_cliente` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `titular` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `flg_cliente` TINYINT UNSIGNED NOT NULL,
    `flg_cuenta` BIGINT UNSIGNED NOT NULL,
    `tipo_monto` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL,
    `anio_cast` SMALLINT UNSIGNED NULL,
    `dpto` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `zona` VARCHAR(20) COLLATE utf8mb4_unicode_ci NULL,
    `ran_cap` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL,
    `fecha_nacimiento` DATE NULL,
    `sexo` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL,
    `estado_civil` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `origen` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `entidad` VARCHAR(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `cosecha` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `cons_deuda_k` DECIMAL(18,2) NULL,
    `cons_intereses` DECIMAL(18,2) NULL,
    `cons_deuda_total` DECIMAL(18,2) NULL,
    PRIMARY KEY (`assignment_client_id`),
    UNIQUE KEY `uq_asignacion_cliente_generation_cosecha_documento`
        (`generation_id`, `cosecha`, `documento_cliente`),
    KEY `idx_asignacion_cliente_generation` (`generation_id`),
    KEY `idx_asignacion_cliente_cosecha_documento` (`cosecha`, `documento_cliente`),
    CONSTRAINT `fk_asignacion_cliente_generacion`
        FOREIGN KEY (`generation_id`) REFERENCES `kp_gold`.`asignacion_mensual_generaciones` (`generation_id`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_gold`.`asignacion_mensual_operaciones` (
    `assignment_client_id` BIGINT UNSIGNED NOT NULL,
    `operacion_id` BIGINT UNSIGNED NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `source_raw_id` BIGINT UNSIGNED NOT NULL,
    `identificador_origen` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `cosecha_origen` VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `moneda_original` VARCHAR(20) COLLATE utf8mb4_unicode_ci NULL,
    `moneda_resuelta` VARCHAR(10) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `capital_original` DECIMAL(18,2) NULL,
    `deuda_total_original` DECIMAL(18,2) NULL,
    `tipo_cambio` DECIMAL(18,8) NULL,
    `fecha_tipo_cambio` DATE NULL,
    `tipo_cambio_clase` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NULL,
    `fuente_tipo_cambio` VARCHAR(255) COLLATE utf8mb4_unicode_ci NULL,
    `capital_convertido_pen` DECIMAL(18,2) NULL,
    `deuda_total_convertida_pen` DECIMAL(18,2) NULL,
    PRIMARY KEY (`assignment_client_id`, `operacion_id`),
    KEY `idx_asignacion_operacion_trace` (`batch_id`, `source_raw_id`),
    KEY `idx_asignacion_operacion_moneda` (`batch_id`, `moneda_resuelta`),
    CONSTRAINT `fk_asignacion_operacion_cliente`
        FOREIGN KEY (`assignment_client_id`) REFERENCES `kp_gold`.`asignacion_mensual_clientes` (`assignment_client_id`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_gold`.`asignacion_mensual_conciliacion` (
    `generation_id` BIGINT UNSIGNED NOT NULL,
    `batch_id` BIGINT UNSIGNED NOT NULL,
    `entidad` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cosecha` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `moneda_origen` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `operation_count` BIGINT UNSIGNED NOT NULL,
    `client_count` BIGINT UNSIGNED NOT NULL,
    `capital_original_pen` DECIMAL(18,2) NULL,
    `capital_original_usd` DECIMAL(18,2) NULL,
    `capital_convertido_pen` DECIMAL(18,2) NULL,
    `deuda_total_convertida_pen` DECIMAL(18,2) NULL,
    `componentes_no_capital_pen` DECIMAL(18,2) NULL,
    `operations_without_currency` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `operations_without_debt_total` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `operations_without_exchange_rate` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `assignment_capital_pen` DECIMAL(18,2) NULL,
    `assignment_debt_total_pen` DECIMAL(18,2) NULL,
    `difference_capital_pen` DECIMAL(18,2) NULL,
    `difference_debt_total_pen` DECIMAL(18,2) NULL,
    `status` VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `warnings` TEXT COLLATE utf8mb4_unicode_ci NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`generation_id`, `batch_id`, `entidad`, `cosecha`, `moneda_origen`),
    KEY `idx_asignacion_conciliacion_status` (`generation_id`, `status`),
    CONSTRAINT `fk_asignacion_conciliacion_generacion`
        FOREIGN KEY (`generation_id`) REFERENCES `kp_gold`.`asignacion_mensual_generaciones` (`generation_id`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `kp_gold`.`asignacion_mensual_anomalias` (
    `anomaly_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `generation_id` BIGINT UNSIGNED NOT NULL,
    `code` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `cosecha` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `documento_cliente` VARCHAR(100) COLLATE utf8mb4_unicode_ci NULL,
    `message` VARCHAR(1000) COLLATE utf8mb4_unicode_ci NOT NULL,
    `created_at` DATETIME NOT NULL,
    PRIMARY KEY (`anomaly_id`),
    KEY `idx_asignacion_anomalias_generation` (`generation_id`, `code`),
    CONSTRAINT `fk_asignacion_anomalia_generacion`
        FOREIGN KEY (`generation_id`) REFERENCES `kp_gold`.`asignacion_mensual_generaciones` (`generation_id`)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- La referencia activa se agrega después de crear generaciones para evitar el
-- ciclo DDL. El publicador debe actualizar puntero y estado en una transacción.
ALTER TABLE `kp_control`.`asignacion_periodos`
    ADD CONSTRAINT `fk_asignacion_periodo_generacion_activa`
        FOREIGN KEY (`active_generation_id`, `periodo`)
        REFERENCES `kp_gold`.`asignacion_mensual_generaciones` (`generation_id`, `periodo`)
        ON UPDATE RESTRICT ON DELETE RESTRICT;

-- El índice único limita PUBLISHED a una generación por periodo. Estos triggers
-- impiden además que el puntero activo señale DRAFT/FAILED/SUPERSEDED o que una
-- generación activa deje de ser PUBLISHED. El intercambio se realiza en una
-- transacción: liberar puntero, superseder anterior, publicar nueva y apuntar.
DELIMITER $$

CREATE TRIGGER `kp_control`.`trg_asignacion_periodo_active_generation_published`
BEFORE UPDATE ON `kp_control`.`asignacion_periodos`
FOR EACH ROW
BEGIN
    DECLARE active_status VARCHAR(20);

    IF NEW.`active_generation_id` IS NOT NULL THEN
        SELECT `estado` INTO active_status
        FROM `kp_gold`.`asignacion_mensual_generaciones`
        WHERE `generation_id` = NEW.`active_generation_id`
          AND `periodo` = NEW.`periodo`;

        IF active_status IS NULL OR active_status <> 'PUBLISHED' THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'La generación activa debe estar PUBLISHED y pertenecer al periodo.';
        END IF;
    END IF;
END$$

CREATE TRIGGER `kp_gold`.`trg_asignacion_generacion_active_remains_published`
BEFORE UPDATE ON `kp_gold`.`asignacion_mensual_generaciones`
FOR EACH ROW
BEGIN
    IF OLD.`estado` = 'PUBLISHED' AND NEW.`estado` <> 'PUBLISHED'
       AND EXISTS (
           SELECT 1
           FROM `kp_control`.`asignacion_periodos`
           WHERE `active_generation_id` = OLD.`generation_id`
       ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'La generación activa no puede dejar de estar PUBLISHED.';
    END IF;
END$$

DELIMITER ;

-- Esta fase no altera Bronze ni Silver. Como recomendación futura, revisar en
-- una réplica el índice `(batch_id, cosecha, documento_cliente)` de
-- `kp_silver.cartera_operaciones` con INFORMATION_SCHEMA y EXPLAIN antes de
-- proponer un script DDL separado y aprobado.

-- Los catálogos se insertan una vez, en una transacción posterior al DDL. Un
-- duplicado o una discrepancia debe abortar la carga: no se ignora ni actualiza.
START TRANSACTION;

INSERT INTO `kp_control`.`cartera_cosechas`
    (`cosecha`, `entidad`, `fecha_compra`, `origen`, `created_at`, `updated_at`)
VALUES
    ('BBVA1', 'BBVA', '2020-09-30', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BBVA2', 'BBVA', '2020-09-30', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BBVA3', 'BBVA', '2020-11-01', 'FONDO I', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BBVA4', 'BBVA', '2020-11-01', 'FONDO I', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BBVA5', 'BBVA', '2020-11-27', 'FONDO I', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BBVA6', 'BBVA', '2020-12-30', 'FONDO I', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BBVA7', 'BBVA', '2020-12-30', 'FONDO II', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('BBVA8', 'BBVA', '2021-04-16', 'FONDO II', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CAJAAQP1', 'CAJA_AREQUIPA', '2019-04-29', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CAJAAQP2', 'CAJA_AREQUIPA', '2019-07-24', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CAJAAQP3', 'CAJA_AREQUIPA', '2020-12-22', 'FONDO I', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CAJAAQP4', 'CAJA_AREQUIPA', '2025-10-22', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CAJAAQP5', 'CAJA_AREQUIPA', '2025-12-22', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('COMPARTAMOS_1', 'COMPARTAMOS', '2024-12-17', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('COMPARTAMOS_2', 'COMPARTAMOS', '2025-12-29', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('COMPARTAMOS_3', 'COMPARTAMOS', '2026-07-21', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA', '2019-12-09', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_2', 'CONFIANZA', '2020-12-22', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_3', 'CONFIANZA', '2021-11-30', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_4', 'CONFIANZA', '2022-07-30', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_5', 'CONFIANZA', '2022-12-01', 'FONDO II', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_6', 'CONFIANZA', '2023-06-30', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_7', 'CONFIANZA', '2023-09-12', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_8', 'CONFIANZA', '2023-11-28', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_9', 'CONFIANZA', '2023-12-07', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_10', 'CONFIANZA', '2024-02-29', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_11', 'CONFIANZA', '2024-05-31', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA_12', 'CONFIANZA', '2024-12-26', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('WANDOO_1', 'WANDOO', '2026-04-10', 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('SEMBRANDO', NULL, NULL, 'KP INVEST', UTC_TIMESTAMP(), UTC_TIMESTAMP());

INSERT INTO `kp_control`.`zonas_departamento`
    (`departamento`, `zona`, `created_at`, `updated_at`)
VALUES
    ('AMAZONAS', 'ORIENTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('ANCASH', 'NORTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('APURIMAC', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('AREQUIPA', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('AYACUCHO', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CAJAMARCA', 'NORTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CALLAO', 'CENTRO', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CUSCO', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('HUANCAVELICA', 'CENTRO', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('HUANUCO', 'CENTRO', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('ICA', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('JUNIN', 'CENTRO', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('LA LIBERTAD', 'NORTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('LAMBAYEQUE', 'NORTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('LIMA', 'CENTRO', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('LORETO', 'ORIENTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('MADRE DE DIOS', 'ORIENTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('MOQUEGUA', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('PASCO', 'CENTRO', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('PIURA', 'NORTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('PUNO', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('SAN MARTIN', 'ORIENTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('TACNA', 'SUR', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('TUMBES', 'NORTE', UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('UCAYALI', 'ORIENTE', UTC_TIMESTAMP(), UTC_TIMESTAMP());

-- Decisión funcional confirmada el 2026-10-26: la cosecha WANDOO_1 está
-- expresada en PEN. Esta carga no aplica
-- el criterio a otras cosechas Wandoo presentes o futuras.
INSERT INTO `kp_control`.`asignacion_politicas_moneda`
    (`entidad`, `cosecha_scope`, `moneda_confirmada`, `evidence`, `is_active`, `created_at`, `updated_at`)
VALUES
    ('WANDOO', 'WANDOO_1', 'PEN', 'confirmación funcional del negocio del 2026-10-26', 1,
     UTC_TIMESTAMP(), UTC_TIMESTAMP());

-- Aliases históricos de Confianza propuestos individualmente. Deben contrastarse
-- primero con el inventario de SQL 060: cada origen debe aparecer una vez, sin
-- otra equivalencia activa. Un duplicado o una divergencia aborta la transacción
-- y queda para revisión explícita; no se oculta durante la instalación.
INSERT INTO `kp_control`.`asignacion_cosecha_aliases`
    (`entidad`, `cosecha_origen`, `cosecha_canonica`, `evidence`, `is_active`, `created_at`, `updated_at`)
VALUES
    ('CONFIANZA', 'CONFIANZA 2', 'CONFIANZA_2', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 3', 'CONFIANZA_3', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 4', 'CONFIANZA_4', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 5', 'CONFIANZA_5', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 6', 'CONFIANZA_6', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 7', 'CONFIANZA_7', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 8', 'CONFIANZA_8', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 9', 'CONFIANZA_9', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 10', 'CONFIANZA_10', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 11', 'CONFIANZA_11', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP()),
    ('CONFIANZA', 'CONFIANZA 12', 'CONFIANZA_12', 'equivalencia histórica; validar inventario SQL 060', 1, UTC_TIMESTAMP(), UTC_TIMESTAMP());

COMMIT;

-- Resultado auditable por el log de instalación del cliente MySQL.
SELECT 'monthly_assignment_foundation_installed' AS installation_result,
       COUNT(*) AS installed_table_count
FROM information_schema.tables
WHERE (table_schema = 'kp_control' AND table_name IN (
        'cartera_cosechas', 'zonas_departamento', 'tipos_cambio',
        'asignacion_politicas_moneda', 'asignacion_cosecha_aliases',
        'asignacion_catalogo_cambios', 'asignacion_periodos',
        'asignacion_periodo_cartera_batch'
      ))
   OR (table_schema = 'kp_gold' AND table_name IN (
        'asignacion_mensual_generaciones', 'asignacion_mensual_clientes',
        'asignacion_mensual_operaciones', 'asignacion_mensual_conciliacion',
        'asignacion_mensual_anomalias'
      ));
