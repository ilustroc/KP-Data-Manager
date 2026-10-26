-- KP Data Manager - Fase 1: verificación posterior de instalación.
-- SOLO LECTURA. Ejecutar después de SQL 059 y archivar la salida del cliente.

-- 1. Deben existir exactamente las 13 tablas del alcance.
SELECT COUNT(*) AS installed_table_count,
       CASE WHEN COUNT(*) = 13 THEN 'PASS' ELSE 'FAIL' END AS installation_status
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

-- 2. Deben estar presentes las FKs de trazabilidad y el puntero activo.
SELECT table_schema, table_name, constraint_name, column_name,
       referenced_table_schema, referenced_table_name, referenced_column_name
FROM information_schema.key_column_usage
WHERE (table_schema = 'kp_control' AND table_name IN ('asignacion_periodo_cartera_batch', 'asignacion_periodos'))
   OR (table_schema = 'kp_gold' AND table_name IN (
        'asignacion_mensual_generaciones', 'asignacion_mensual_clientes',
        'asignacion_mensual_operaciones', 'asignacion_mensual_conciliacion',
        'asignacion_mensual_anomalias'
      ))
ORDER BY table_schema, table_name, constraint_name, ordinal_position;

-- 3. Un único estado PUBLISHED por periodo se protege mediante índice único
-- sobre la columna generada official_periodo.
SELECT table_schema, table_name, index_name, non_unique, seq_in_index, column_name
FROM information_schema.statistics
WHERE table_schema = 'kp_gold'
  AND table_name = 'asignacion_mensual_generaciones'
  AND index_name IN ('uq_asignacion_generacion_official_periodo', 'uq_asignacion_generacion_id_periodo')
ORDER BY index_name, seq_in_index;

SELECT trigger_schema, trigger_name, event_object_schema, event_object_table,
       action_timing, event_manipulation
FROM information_schema.triggers
WHERE (trigger_schema = 'kp_control' AND trigger_name = 'trg_asignacion_periodo_active_generation_published')
   OR (trigger_schema = 'kp_gold' AND trigger_name = 'trg_asignacion_generacion_active_remains_published')
ORDER BY trigger_schema, trigger_name;

-- 4. La instalación no debe crear ninguna generación ni fila mensual.
SELECT 'asignacion_mensual_generaciones' AS table_name, COUNT(*) AS row_count
FROM kp_gold.asignacion_mensual_generaciones
UNION ALL
SELECT 'asignacion_mensual_clientes', COUNT(*)
FROM kp_gold.asignacion_mensual_clientes
UNION ALL
SELECT 'asignacion_mensual_operaciones', COUNT(*)
FROM kp_gold.asignacion_mensual_operaciones
UNION ALL
SELECT 'asignacion_mensual_conciliacion', COUNT(*)
FROM kp_gold.asignacion_mensual_conciliacion
UNION ALL
SELECT 'asignacion_mensual_anomalias', COUNT(*)
FROM kp_gold.asignacion_mensual_anomalias;

-- 5. Conteos exactos de catálogos y política WANDOO_1 = PEN.
SELECT 'cartera_cosechas' AS catalog_name, COUNT(*) AS row_count, 30 AS expected_row_count
FROM kp_control.cartera_cosechas
UNION ALL
SELECT 'zonas_departamento', COUNT(*), 25
FROM kp_control.zonas_departamento
UNION ALL
SELECT 'asignacion_cosecha_aliases', COUNT(*), 11
FROM kp_control.asignacion_cosecha_aliases
UNION ALL
SELECT 'asignacion_politicas_moneda', COUNT(*), 1
FROM kp_control.asignacion_politicas_moneda;

SELECT cosecha, entidad, fecha_compra, origen
FROM kp_control.cartera_cosechas
WHERE cosecha = 'CONFIANZA_5';

SELECT entidad, cosecha_scope, moneda_confirmada, is_active, evidence
FROM kp_control.asignacion_politicas_moneda
WHERE entidad = 'WANDOO'
  AND cosecha_scope = 'WANDOO_1';

-- 6. Los once aliases Confianza deben estar activos y apuntar uno a uno.
SELECT cosecha_origen, cosecha_canonica, is_active
FROM kp_control.asignacion_cosecha_aliases
WHERE entidad = 'CONFIANZA'
ORDER BY cosecha_origen;

-- 7. No debe existir alias activo que habilite CONFIANZA_1.
SELECT COUNT(*) AS confianza_1_active_aliases,
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS confianza_1_status
FROM kp_control.asignacion_cosecha_aliases
WHERE entidad = 'CONFIANZA'
  AND cosecha_origen = 'CONFIANZA_1'
  AND is_active = 1;
