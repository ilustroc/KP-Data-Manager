-- KP Data Manager - Fase 1: preflight de instalación de asignación mensual.
-- SOLO LECTURA. Compatible con MySQL 5.7.33 y MySQL 8.0.
-- Ejecutar y archivar su salida antes de aplicar SQL 059. No expone personas.

-- 1. Servidor y configuración relevante para DDL/InnoDB.
SELECT VERSION() AS mysql_version,
       @@version_comment AS version_comment,
       @@default_storage_engine AS default_storage_engine,
       @@character_set_server AS character_set_server,
       @@collation_server AS collation_server;

-- 2. Los tres esquemas deben existir; SQL 059 no los crea.
SELECT schema_name, default_character_set_name, default_collation_name
FROM information_schema.schemata
WHERE schema_name IN ('kp_control', 'kp_silver', 'kp_gold')
ORDER BY schema_name;

-- 3. Las 13 tablas deben no existir antes de ejecutar SQL 059.
SELECT table_schema, table_name, engine, table_collation
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
      ))
ORDER BY table_schema, table_name;

-- 4. Fuentes requeridas: InnoDB, estructura y collations antes de crear FKs.
SELECT table_schema, table_name, engine, table_collation
FROM information_schema.tables
WHERE (table_schema, table_name) IN (
    ('kp_control', 'import_batch'),
    ('kp_silver', 'cartera_operaciones'),
    ('kp_silver', 'search_personas')
)
ORDER BY table_schema, table_name;

-- 5. Columnas que usa la conciliación; revisar tipos/collations reales.
SELECT table_schema, table_name, column_name, column_type, is_nullable,
       column_key, character_set_name, collation_name
FROM information_schema.columns
WHERE (table_schema = 'kp_silver' AND table_name = 'cartera_operaciones'
       AND column_name IN ('entidad', 'cosecha', 'documento_cliente', 'operacion',
                           'identificador_origen', 'moneda', 'saldo_capital',
                           'deuda_total', 'batch_id', 'source_raw_id'))
   OR (table_schema = 'kp_silver' AND table_name = 'search_personas'
       AND column_name IN ('documento', 'batch_id', 'source_code'))
   OR (table_schema = 'kp_control' AND table_name = 'import_batch'
       AND column_name IN ('batch_id', 'tipo', 'entidad', 'dataset_code',
                           'source_code', 'refresh_mode', 'estado', 'published_at',
                           'rows_published'))
ORDER BY table_schema, table_name, ordinal_position;

-- 6. Índices disponibles para la conciliación. No crear índices en producción
-- durante este preflight; evaluar EXPLAIN únicamente en réplica autorizada.
SELECT table_schema, table_name, index_name, non_unique, seq_in_index, column_name
FROM information_schema.statistics
WHERE table_schema = 'kp_silver'
  AND table_name IN ('cartera_operaciones', 'search_personas')
ORDER BY table_name, index_name, seq_in_index;

-- 7. Batches candidatos: las cinco carteras deben estar COMPLETADO/CARTERA;
-- PERSONAS 44 debe ser PERSONAS/BASE_PERSONAS, publicado y modo permitido.
SELECT batch_id, tipo, entidad, dataset_code, source_code, refresh_mode,
       estado, published_at, rows_published
FROM kp_control.import_batch
WHERE batch_id IN (7, 14, 21, 26, 29, 44)
ORDER BY batch_id;

-- 8. Inventario de cosechas Confianza batch 26, sin exponer DNI.
SELECT cosecha AS cosecha_origen, COUNT(*) AS operaciones,
       COUNT(DISTINCT documento_cliente) AS documentos
FROM kp_silver.cartera_operaciones
WHERE entidad = 'CONFIANZA'
  AND batch_id = 26
GROUP BY cosecha
ORDER BY cosecha;

-- 9. Cobertura financiera por entidad, cosecha y moneda, sin solarización.
SELECT entidad, batch_id, cosecha, moneda, COUNT(*) AS operaciones,
       COUNT(DISTINCT documento_cliente) AS documentos,
       SUM(saldo_capital) AS capital_original,
       SUM(deuda_total) AS deuda_total_original
FROM kp_silver.cartera_operaciones
WHERE (entidad = 'BBVA' AND batch_id = 7)
   OR (entidad = 'CAJA_AREQUIPA' AND batch_id = 14)
   OR (entidad = 'COMPARTAMOS' AND batch_id = 21)
   OR (entidad = 'CONFIANZA' AND batch_id = 26)
   OR (entidad = 'WANDOO' AND batch_id = 29)
GROUP BY entidad, batch_id, cosecha, moneda
ORDER BY entidad, batch_id, cosecha, moneda;

-- 10. WANDOO_1 debe contrastar 13,042 clientes, 13,044 operaciones,
-- capital/deuda S/ 6,615,373.31 y componentes no capital S/ 0.00.
SELECT COUNT(*) AS operaciones,
       COUNT(DISTINCT documento_cliente) AS documentos,
       SUM(saldo_capital) AS capital,
       SUM(deuda_total) AS deuda_total,
       SUM(deuda_total - saldo_capital) AS componentes_no_capital,
       SUM(identificador_origen LIKE 'WAN1:%') AS operaciones_con_wan1,
       SUM(identificador_origen IS NULL OR identificador_origen NOT LIKE 'WAN1:%') AS operaciones_sin_wan1
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND batch_id = 29
  AND cosecha = 'WANDOO_1';

-- 11. Posibles duplicados: revisar causa antes de excluir; no devuelve claves.
SELECT entidad, cosecha, COUNT(*) AS grupos_duplicados,
       SUM(filas) AS filas_involucradas
FROM (
    SELECT entidad, cosecha, documento_cliente, operacion, identificador_origen,
           COUNT(*) AS filas
    FROM kp_silver.cartera_operaciones
    WHERE (entidad = 'BBVA' AND batch_id = 7)
       OR (entidad = 'CAJA_AREQUIPA' AND batch_id = 14)
       OR (entidad = 'COMPARTAMOS' AND batch_id = 21)
       OR (entidad = 'CONFIANZA' AND batch_id = 26)
       OR (entidad = 'WANDOO' AND batch_id = 29)
    GROUP BY entidad, cosecha, documento_cliente, operacion, identificador_origen
    HAVING COUNT(*) > 1
) AS duplicate_groups
GROUP BY entidad, cosecha
ORDER BY entidad, cosecha;

-- 12. Post-instalación: las 13 tablas, todos sus índices y FKs deben figurar.
SELECT tables.table_schema, tables.table_name, tables.engine,
       COUNT(DISTINCT stats.index_name) AS index_count,
       COUNT(DISTINCT refs.constraint_name) AS foreign_key_count
FROM information_schema.tables AS tables
LEFT JOIN information_schema.statistics AS stats
  ON stats.table_schema = tables.table_schema
 AND stats.table_name = tables.table_name
LEFT JOIN information_schema.key_column_usage AS refs
  ON refs.table_schema = tables.table_schema
 AND refs.table_name = tables.table_name
 AND refs.referenced_table_name IS NOT NULL
WHERE (tables.table_schema = 'kp_control' AND tables.table_name LIKE 'asignacion_%')
   OR (tables.table_schema = 'kp_control' AND tables.table_name IN (
        'cartera_cosechas', 'zonas_departamento', 'tipos_cambio'
      ))
   OR (tables.table_schema = 'kp_gold' AND tables.table_name LIKE 'asignacion_mensual_%')
GROUP BY tables.table_schema, tables.table_name, tables.engine
ORDER BY tables.table_schema, tables.table_name;
